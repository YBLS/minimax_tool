"""Generation service: shared engine that turns a Config + prompt + params
into a list of persisted media files.

Four modules (image / voice / music / video) are configured via the same
`request_template` and `response_parser` shape, so we only need one engine.

The template substitution language is intentionally tiny:
  {{prompt}}    — the user's prompt
  {{api_key}}   — the decrypted API key for this config
  {{model}}     — the config's model
  {{any_key}}   — user-supplied params (or default_params), with `|default` for fallback

Response parsers supported:
  openai_image  —  resp.data[*] with .url or .b64_json
  openai_audio  —  resp.data[*] with .url (mp3 / wav / ...)
  openai_video  —  resp.data[*] with .url
  binary        —  whole response body is the file (e.g. /audio/speech returns bytes)
  jsonpath      —  custom: {items_path, url_field, b64_field?, default_ext?}
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.crypto import decrypt_str
from app.schemas import OutputFile
from app.security import redact_sensitive, validate_outbound_url
from app.utils.files import (
    _safe_filename,
    abs_from_url_path,
    build_path,
    download_to_disk,
    ext_from_content_type,
    ext_from_url,
    file_kind,
    hash_file,
    media_url,
)

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Wraps upstream / network failures with a friendly message."""

    def __init__(
        self,
        message: str,
        *,
        http_status: Optional[int] = None,
        upstream_body: Optional[Any] = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.upstream_body = upstream_body


# --------------------------- template engine ---------------------------

# Placeholder syntax: `{{key:typename|default}}`
#   typename:  s (string, default) | i (int) | n (number/float) | b (bool) | j (json literal)
#   default:   optional fallback used when ctx lookup returns None/empty
# Examples:
#   {{model}}                  → string, default ""
#   {{n:i|1}}                  → int, default 1
#   {{prompt_optimizer:b|false}} → bool, default false
#   {{aspect_ratio:s|1:1}}     → string, default "1:1"
_PLACEHOLDER_RE = re.compile(
    r"\{\{\s*([\w.\-]+)(?::(s|i|n|b|j))?(?:\|([^{}]*))?\s*\}\}"
)


def _resolve(key: str, ctx: dict[str, Any]) -> Any:
    """Look up `a.b.c` against ctx, returning None if missing."""
    cur: Any = ctx
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _coerce(value: Any, type_hint: str) -> Any:
    """Best-effort coerce `value` to JSON-typed `type_hint`."""
    if value is None or value == "":
        return None
    if type_hint == "b":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        s = str(value).strip().lower()
        return s in ("true", "1", "yes", "on")
    if type_hint == "i":
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return 0
    if type_hint == "n":
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return 0.0
    if type_hint == "j":
        return value  # take as-is (caller will json.dumps)
    # default: string
    if isinstance(value, str):
        return value
    return str(value)


def render_template(obj: Any, ctx: dict[str, Any]) -> Any:
    """Recursively substitute {{...}} placeholders.

    - For string slots (no `{{...}}` outside of a JSON quoted position) the
      placeholder text in the template is inside quotes, so the rendered
      literal needs to be a *raw* JSON fragment (no surrounding quotes).
    - For typed placeholders (`{{n:i|1}}`) the renderer coerces the value
      to the requested type and renders a JSON literal (e.g. `1`, `false`).
    """
    if isinstance(obj, str):
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            type_hint = m.group(2) or "s"
            default_raw = m.group(3)
            val = _resolve(key, ctx)
            if val is None or val == "":
                # Use the default
                if default_raw is None:
                    return ""
                coerced = _coerce(default_raw, type_hint)
            else:
                coerced = _coerce(val, type_hint)

            if coerced is None:
                return ""
            if type_hint == "b":
                return "true" if coerced else "false"
            if type_hint in ("i", "n"):
                if isinstance(coerced, float) and coerced.is_integer():
                    return str(int(coerced))
                return str(coerced)
            if type_hint == "j":
                return json.dumps(coerced)
            # string — drop the value as-is (template's surrounding quotes are JSON syntax)
            return str(coerced)
        return _PLACEHOLDER_RE.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: render_template(v, ctx) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_template(v, ctx) for v in obj]
    return obj


def _drop_unset(obj: Any) -> Any:
    """Remove empty strings / empty dicts from a rendered template (clean payloads)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v2 = _drop_unset(v)
            if v2 == "" or v2 is None:
                continue
            if isinstance(v2, (dict, list)) and len(v2) == 0:
                continue
            out[k] = v2
        return out
    if isinstance(obj, list):
        return [_drop_unset(v) for v in obj if v not in ("", None)]
    return obj


# --------------------------- engine ---------------------------

@dataclass
class ResolvedConfig:
    id: int
    module: str
    api_key: str
    base_url: str
    endpoint_path: str
    model: str
    request_template: dict[str, Any]
    response_parser: dict[str, Any]
    default_params: dict[str, Any]


async def load_config(module: str, config_id: Optional[int] = None) -> ResolvedConfig:
    """Resolve a per-module config to a fully-decrypted ResolvedConfig.

    The API key now lives on key_providers (a sibling table), not on
    api_configs. The linking rules are:

      1. If the config row has key_provider_id set, use that provider.
      2. Otherwise, count enabled key_providers:
         * 0  → no key configured anywhere → GenerationError.
         * 1  → auto-bind to that one (the "single shared key" path).
         * 2+ → ambiguous; tell the user to pick one explicitly.
    """
    from app.database import fetch, fetchrow
    import json

    if config_id is not None:
        row = await fetchrow(
            "SELECT * FROM api_configs WHERE id = $1 AND module = $2 AND enabled = TRUE", config_id, module
        )
    else:
        row = await fetchrow(
            "SELECT * FROM api_configs WHERE module = $1 AND enabled = TRUE ORDER BY id ASC LIMIT 1",
            module,
        )
    if not row:
        raise GenerationError(f"No config found for module={module}")

    # Pick the provider.
    provider_id = row.get("key_provider_id")
    api_key = ""
    if provider_id is not None:
        prow = await fetchrow(
            "SELECT api_key_encrypted FROM key_providers WHERE id = $1", provider_id
        )
        if prow and prow["api_key_encrypted"]:
            api_key = decrypt_str(prow["api_key_encrypted"])
    else:
        providers = await fetch(
            "SELECT id, api_key_encrypted FROM key_providers WHERE enabled = TRUE ORDER BY id ASC"
        )
        if not providers:
            raise GenerationError(
                "No API key configured. Open Config Center → API Keys and create one."
            )
        if len(providers) > 1:
            names = await fetch(
                "SELECT id, name FROM key_providers WHERE enabled = TRUE ORDER BY id ASC"
            )
            listing = ", ".join(
                f"{p['name']} (#{p['id']})" for p in names
            ) if names else f"{len(providers)} providers"
            raise GenerationError(
                f"Module '{module}' has no key_provider_id set and there are "
                f"{len(providers)} enabled providers ({listing}). "
                f"Edit the config and pick one explicitly."
            )
        # Exactly one — auto-bind.
        api_key = decrypt_str(providers[0]["api_key_encrypted"]) if providers[0]["api_key_encrypted"] else ""

    def _coerce(v):
        # Legacy data may have been double-/triple-encoded as JSONB strings
        # (the previous asyncpg codec + ::jsonb cast interacted badly). Un-nest
        # up to 3 levels so old rows still load.
        cur = v
        for _ in range(3):
            if not isinstance(cur, str):
                break
            try:
                cur = json.loads(cur)
            except json.JSONDecodeError:
                return {}
        return cur if isinstance(cur, dict) else {}

    return ResolvedConfig(
        id=row["id"],
        module=row["module"],
        api_key=api_key,
        base_url=row["base_url"],
        endpoint_path=row["endpoint_path"],
        model=row["model"],
        request_template=_coerce(row["request_template"]),
        response_parser=_coerce(row["response_parser"]),
        default_params=_coerce(row["default_params"]),
    )


def build_context(cfg: ResolvedConfig, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
    merged = {**cfg.default_params, **params}
    return {
        "prompt": prompt,
        "api_key": cfg.api_key,
        "model": cfg.model,
        **merged,
    }


def build_request(cfg: ResolvedConfig, prompt: str, params: dict[str, Any]) -> dict[str, Any]:
    """Render the user template into a fully-substituted request object.

    Two-step:
      1. `render_template` substitutes `{{...}}` placeholders. The result
         dict has all leaf values as strings (because re.sub is string-based
         and the template's quotes are JSON syntax).
      2. `_restore_typed_values` walks the dict and replaces each leaf
         string with the original typed value from the context. This
         ensures the wire payload has correct JSON types (true, 1, 1.5)
         rather than the strings "true", "1", "1.5" that the regex would
         produce.
    """
    ctx = build_context(cfg, prompt, params)
    rendered = render_template(cfg.request_template, ctx)
    rendered = _drop_unset(rendered)
    out = _restore_typed_values(rendered, ctx)
    return _apply_module_post_hooks(cfg, out, ctx)


def _apply_module_post_hooks(
    cfg: ResolvedConfig, request_obj: dict[str, Any], ctx: dict[str, Any]
) -> dict[str, Any]:
    """Strip / coerce module-specific fields for the wire payload.

    - `video` (submode == `fl2v`): `fast_pretreatment` is not part of the FL2V
      schema. Defensive: remove it from the body if the user accidentally
      supplied it.
    - `video` (submode in {t2v, i2v}): make sure `fast_pretreatment` is a
      proper bool in the body even when the user didn't supply it (the
      template default renders the string "false" otherwise).
    """
    if cfg.module == "video" and isinstance(request_obj.get("body"), dict):
        body = request_obj["body"]
        submode = ctx.get("submode")
        if submode == "fl2v":
            body.pop("fast_pretreatment", None)
        elif submode in ("t2v", "i2v"):
            # Coerce the placeholder-rendered string to a real bool.
            if "fast_pretreatment" in body and isinstance(body["fast_pretreatment"], str):
                body["fast_pretreatment"] = body["fast_pretreatment"].lower() == "true"
    return request_obj


def _restore_typed_values(obj: Any, ctx: dict[str, Any], key_path: tuple[str, ...] = ()) -> Any:
    """Recursively replace string leaves with their typed counterparts from ctx.

    For each leaf string, looks up the key (the last segment of the path)
    in the flat ctx. If ctx has a non-string value for that key, returns
    that typed value instead of the string the regex produced.
    """
    if isinstance(obj, dict):
        return {k: _restore_typed_values(v, ctx, key_path + (k,)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore_typed_values(v, ctx, key_path) for v in obj]
    if isinstance(obj, str) and key_path:
        leaf = key_path[-1]
        if leaf in ctx and not isinstance(ctx[leaf], str):
            return ctx[leaf]
    return obj


# --------------------------- HTTP + parse ---------------------------

async def call_upstream(
    cfg: ResolvedConfig, request_obj: dict[str, Any]
) -> tuple[Optional[bytes], Optional[dict[str, Any]], dict[str, str]]:
    """Execute the request. Returns (body_bytes, parsed_json, headers).

    Raises GenerationError on non-2xx responses, attaching the parsed body for debugging.
    """
    settings = get_settings()
    method = (request_obj.get("method") or "POST").upper()
    headers = dict(request_obj.get("headers") or {})
    body = request_obj.get("body")
    query = request_obj.get("query")
    url = cfg.base_url.rstrip("/") + "/" + cfg.endpoint_path.lstrip("/")
    try:
        await validate_outbound_url(url, allow_private=settings.allow_private_upstreams)
    except ValueError as exc:
        raise GenerationError(str(exc)) from exc

    timeout = httpx.Timeout(settings.request_timeout, connect=30.0)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=query)
        elif method == "POST":
            data = body if isinstance(body, (str, bytes)) else json.dumps(body)
            if isinstance(body, dict) and "Content-Type" not in {h.title() for h in headers}:
                headers.setdefault("Content-Type", "application/json")
            resp = await client.post(url, headers=headers, content=data, params=query)
        else:
            resp = await client.request(method, url, headers=headers, params=query)

    headers_out = {k: v for k, v in resp.headers.items()}

    if resp.status_code >= 400:
        # Try to surface a useful error message
        ct = resp.headers.get("content-type", "").lower()
        if "application/json" in ct:
            try:
                payload = resp.json()
            except Exception:
                payload = resp.text[:1000]
        else:
            payload = (resp.text or "")[:1000]
        msg = f"HTTP {resp.status_code}"
        # Try common error shapes
        if isinstance(payload, dict):
            for key in ("error", "message", "detail", "msg"):
                if key in payload and isinstance(payload[key], (str, dict)):
                    val = payload[key]
                    if isinstance(val, dict) and "message" in val:
                        msg += f": {val['message']}"
                    else:
                        msg += f": {val}"
                    break
        else:
            msg += f": {payload}"
        raise GenerationError(msg, http_status=resp.status_code, upstream_body=payload)

    content_type = resp.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            return None, resp.json(), headers_out
        except Exception as e:
            return resp.content, None, headers_out
    return resp.content, None, headers_out


def _jsonpath_lookup(data: Any, path: str) -> Any:
    """Tiny JSONPath: $ . * [n]

    Accepts paths like:
      $.data.image_urls   → root.data.image_urls
      $.data[*]           → root.data as a list
      $.data[0]           → root.data[0]
      data.image_urls     → root.data.image_urls (no leading $)
      $                   → root
    """
    if not path or path == "$":
        return data
    # Strip a single leading "$" or "$."
    p = path
    if p.startswith("$."):
        p = p[2:]
    elif p == "$":
        return data
    if not p:
        return data
    tokens = [t for t in re.split(r"\.|\[(\d+)\]", p) if t not in (None, "")]
    cur: Any = data
    for tok in tokens:
        if cur is None:
            return None
        if tok == "*":
            if not isinstance(cur, list):
                return None
            return cur
        if tok.isdigit():
            idx = int(tok)
            if isinstance(cur, list) and 0 <= idx < len(cur):
                cur = cur[idx]
            else:
                return None
        else:
            if isinstance(cur, dict) and tok in cur:
                cur = cur[tok]
            else:
                return None
    return cur


# --------------------------- main entry ---------------------------

async def run_generation(
    module: str,
    prompt: str,
    params: dict[str, Any],
    config_id: Optional[int] = None,
) -> tuple[list[OutputFile], dict[str, Any], dict[str, Any], int]:
    """Top-level pipeline. Returns (output_files, request_payload, response_payload, duration_ms)."""
    cfg = await load_config(module, config_id)
    if not cfg.api_key:
        raise GenerationError(
            "API key is empty. Open the Config Center and paste your key first."
        )
    request_obj = build_request(cfg, prompt, params)

    # Async (task-id based) flow, e.g. MiniMax video generation
    if (cfg.response_parser.get("type") or "").lower() == "async_task":
        return await _run_async_task(cfg, request_obj, prompt, params)

    started = time.perf_counter()
    body_bytes, parsed_json, headers = await call_upstream(cfg, request_obj)
    duration_ms = int((time.perf_counter() - started) * 1000)

    files = await _materialize_files(
        module=module,
        prompt=prompt,
        body_bytes=body_bytes,
        parsed_json=parsed_json,
        headers=headers,
        parser=cfg.response_parser,
    )

    response_payload: dict[str, Any]
    if parsed_json is not None:
        try:
            response_payload = _truncate(parsed_json, max_depth=6, max_list=20)
        except Exception:
            response_payload = {"_truncated": True}
    else:
        response_payload = {
            "_binary": True,
            "size": len(body_bytes or b""),
            "content_type": headers.get("content-type", ""),
        }

    request_payload = _truncate(redact_sensitive(request_obj), max_depth=6, max_list=20)
    return files, request_payload, response_payload, duration_ms


async def _run_async_task(
    cfg: ResolvedConfig,
    request_obj: dict[str, Any],
    prompt: str,
    params: dict[str, Any],
) -> tuple[list[OutputFile], dict[str, Any], dict[str, Any], int]:
    """Handle endpoints that return a task_id and need polling."""
    settings = get_settings()
    parser = cfg.response_parser
    poll_interval = float(parser.get("poll_interval", 5.0))
    max_wait = float(parser.get("max_wait", 600.0))
    started = time.perf_counter()

    # 1. Submit
    body_bytes, parsed_json, headers = await call_upstream(cfg, request_obj)
    # MiniMax-style envelope error short-circuit
    if isinstance(parsed_json, dict):
        br = parsed_json.get("base_resp") or {}
        if isinstance(br, dict):
            code = br.get("status_code", 0)
            msg = br.get("status_msg") or ""
            if code not in (0, None, "0", ""):
                raise GenerationError(
                    f"Upstream rejected request (base_resp.code={code}): {msg}"[:1500],
                    upstream_body=parsed_json,
                )
    task_id = _jsonpath_lookup(parsed_json, parser.get("task_id_path", "$.task_id"))
    if not task_id:
        raise GenerationError(
            f"Async endpoint did not return a task_id. Response: {parsed_json!r}"[:1500],
            upstream_body=parsed_json,
        )
    task_id = str(task_id)

    # 2. Poll
    query_path_tmpl = parser.get("query_path", "")
    # Substitute {{task_id}} in path
    query_path = query_path_tmpl.replace("{{task_id}}", task_id)
    query_method = (parser.get("query_method") or "GET").upper()
    query_params = parser.get("query_params") or {}

    def _sub(v):
        if isinstance(v, str):
            return v.replace("{{task_id}}", task_id)
        return v

    query_params_sub = {k: _sub(v) for k, v in query_params.items()}

    deadline = time.perf_counter() + max_wait
    last_status: Any = None
    file_id: Any = None
    last_query_payload: Any = None
    while time.perf_counter() < deadline:
        await asyncio.sleep(poll_interval)
        # Build a synthetic request for the query
        q_headers = dict(request_obj.get("headers") or {})
        # Reuse auth
        q_url = cfg.base_url.rstrip("/") + "/" + query_path.lstrip("/")
        async with httpx.AsyncClient(timeout=settings.request_timeout, follow_redirects=True) as client:
            if query_method == "GET":
                resp = await client.get(q_url, headers=q_headers, params=query_params_sub)
            else:
                resp = await client.request(
                    query_method, q_url, headers=q_headers,
                    json=query_params_sub if isinstance(query_params_sub, dict) else None,
                )
        if resp.status_code >= 400:
            last_status = f"HTTP {resp.status_code}"
            continue
        try:
            qj = resp.json()
        except Exception:
            qj = {"_raw": resp.text[:500]}
        last_query_payload = qj
        last_status = _jsonpath_lookup(qj, "$.status") or _jsonpath_lookup(qj, "$.data.status")
        if isinstance(last_status, str):
            ls = last_status.lower()
        else:
            ls = ""
        if ls in {s.lower() for s in parser.get("terminal_statuses", ["success"])}:
            file_id = _jsonpath_lookup(qj, parser.get("file_id_path", "$.file_id"))
            break
        if ls in {s.lower() for s in parser.get("failed_statuses", ["fail"])}:
            raise GenerationError(f"Upstream task failed: status={last_status}, body={qj}"[:1500])

    if not file_id:
        raise GenerationError(
            f"Async task did not complete within {max_wait:.0f}s (last status={last_status})"
        )

    # 3. Download (or get download URL)
    download_path = parser.get("download_path")
    file_id_str = str(file_id)
    if download_path:
        d_url = cfg.base_url.rstrip("/") + "/" + download_path.lstrip("/")
        d_method = (parser.get("download_method") or "POST").upper()
        d_body = parser.get("download_body") or {}
        if isinstance(d_body, dict):
            d_body = {k: (_sub(v) if isinstance(v, str) else v) for k, v in d_body.items()}
        # Render any {{file_id}} placeholders inside d_body / d_url
        d_url = d_url.replace("{{file_id}}", file_id_str)
        if isinstance(d_body, dict):
            d_body = {
                k: (v.replace("{{file_id}}", file_id_str) if isinstance(v, str) else v)
                for k, v in d_body.items()
            }
        d_headers = dict(request_obj.get("headers") or {})
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            if d_method == "GET":
                d_resp = await client.get(d_url, headers=d_headers, params=d_body)
            else:
                d_resp = await client.request(d_method, d_url, headers=d_headers, json=d_body)
        if d_resp.status_code >= 400:
            raise GenerationError(
                f"File retrieve failed: HTTP {d_resp.status_code}: {d_resp.text[:300]}"
            )
        try:
            dj = d_resp.json()
        except Exception:
            dj = {"_raw": d_resp.text[:500]}
        last_query_payload = dj
        download_url = _jsonpath_lookup(dj, parser.get("download_url_path", "$.file.download_url"))
        if not download_url:
            raise GenerationError(
                f"download_url not found in retrieve response: {dj!r}"[:1500]
            )
    else:
        # Assume file_id is itself a URL
        download_url = file_id

    # 4. Materialize
    ext = parser.get("default_ext", "mp4")
    files = await _materialize_files(
        module=cfg.module,
        prompt=prompt,
        body_bytes=None,
        parsed_json={"data": {"image_urls": [download_url]}},  # reuse jsonpath branch
        headers={},
        parser={
            "type": "jsonpath",
            "items_path": "$.data.image_urls",
            "default_ext": ext,
        },
    )

    duration_ms = int((time.perf_counter() - started) * 1000)
    response_payload = _truncate(
        {
            "task_id": task_id,
            "poll": last_query_payload,
            "download_url": download_url,
        },
        max_depth=6,
        max_list=20,
    )
    request_payload = _truncate(redact_sensitive(request_obj), max_depth=6, max_list=20)
    return files, request_payload, response_payload, duration_ms


def _truncate(obj: Any, *, max_depth: int, max_list: int) -> Any:
    if max_depth <= 0:
        return "…"
    if isinstance(obj, dict):
        return {k: _truncate(v, max_depth=max_depth - 1, max_list=max_list) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate(v, max_depth=max_depth - 1, max_list=max_list) for v in obj[:max_list]]
    if isinstance(obj, str) and len(obj) > 4000:
        return obj[:4000] + "…"
    return obj


async def _materialize_files(
    *,
    module: str,
    prompt: str,
    body_bytes: Optional[bytes],
    parsed_json: Optional[dict[str, Any]],
    headers: dict[str, str],
    parser: dict[str, Any],
) -> list[OutputFile]:
    ptype = (parser.get("type") or "").lower()
    settings = get_settings()
    hint = _safe_filename(prompt)
    out: list[OutputFile] = []

    async def _persist(url: str, ext: str) -> Optional[OutputFile]:
        if not url:
            return None
        dest = build_path(module=module, ext=ext, hint=hint)
        try:
            _, size, mime = await download_to_disk(url, dest, timeout=settings.request_timeout)
        except Exception as exc:  # noqa: BLE001
            logger.warning("download failed for %s: %s", url[:80], exc)
            return OutputFile(
                type=file_kind(ext),
                url=url,  # fall back to source URL
                size=0,
                mime_type="",
                path="",
                source_url=url,
            )
        return OutputFile(
            type=file_kind(ext),
            url=media_url(dest),
            size=size,
            mime_type=mime,
            path=str(dest),
            source_url=url,
        )

    if ptype == "binary":
        # Whole response body is the file
        if not body_bytes:
            raise GenerationError("Binary response was empty")
        ext = parser.get("default_ext") or ext_from_content_type(headers.get("content-type", ""))
        dest = build_path(module=module, ext=ext, hint=hint)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body_bytes)
        size = dest.stat().st_size
        mime = headers.get("content-type", "").split(";")[0].strip() or "application/octet-stream"
        out.append(
            OutputFile(
                type=file_kind(ext),
                url=media_url(dest),
                size=size,
                mime_type=mime,
                path=str(dest),
                source_url=None,
            )
        )
        return out

    if ptype == "minimax_music":
        # Response shape: { data: { audio: "<hex>" } }  or { data: { audio: "<url>" } }
        data = (parsed_json or {}).get("data") if isinstance(parsed_json, dict) else None
        if not isinstance(data, dict):
            raise GenerationError(f"Music: unexpected response shape: {parsed_json!r}"[:1500])
        audio_field = data.get("audio") or ""
        ext = parser.get("default_ext", "mp3")
        if not audio_field:
            raise GenerationError("Music: response.data.audio is empty")
        # Heuristic: if it's all hex chars, decode; else treat as URL
        if re.fullmatch(r"[0-9a-fA-F]+", audio_field) and len(audio_field) > 32:
            raw = bytes.fromhex(audio_field)
            dest = build_path(module=module, ext=ext, hint=hint)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            out.append(
                OutputFile(
                    type=file_kind(ext),
                    url=media_url(dest),
                    size=len(raw),
                    mime_type="",
                    path=str(dest),
                    source_url=None,
                )
            )
        else:
            persisted = await _persist(audio_field, ext_from_url(audio_field, ext))
            if persisted:
                out.append(persisted)
        return out

    if ptype in {"openai_image", "openai_audio", "openai_video", "jsonpath"}:
        # MiniMax-style envelope: surface upstream error early
        if isinstance(parsed_json, dict):
            br = parsed_json.get("base_resp") or {}
            if isinstance(br, dict):
                code = br.get("status_code", 0)
                msg = br.get("status_msg") or ""
                if code not in (0, None, "0", ""):
                    raise GenerationError(
                        f"Upstream rejected request (base_resp.code={code}): {msg}"[:1500],
                        upstream_body=parsed_json,
                    )
        items = _jsonpath_lookup(parsed_json, parser.get("items_path", "$.data[*]"))
        if items is None:
            items = []
        if not isinstance(items, list):
            items = [items]

        default_ext = parser.get("default_ext", "bin")
        url_field = parser.get("url_field", "url")
        b64_field = parser.get("b64_field", "")

        for item in items:
            # Items may be bare strings (URLs) when items_path points to a flat list
            if isinstance(item, str):
                url = item
                b64 = ""
            elif isinstance(item, dict):
                url = item.get(url_field) or ""
                b64 = item.get(b64_field) or "" if b64_field else ""
            else:
                continue
            if b64 and not url:
                raw = base64.b64decode(b64)
                dest = build_path(module=module, ext=default_ext, hint=hint)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                out.append(
                    OutputFile(
                        type=file_kind(default_ext),
                        url=media_url(dest),
                        size=len(raw),
                        mime_type="",
                        path=str(dest),
                        source_url=None,
                    )
                )
                continue
            if not url:
                continue
            ext = ext_from_url(url, default=default_ext)
            persisted = await _persist(url, ext)
            if persisted:
                out.append(persisted)

        if not out:
            snippet = (parsed_json or {"_binary": True, "size": len(body_bytes or b"")})
            try:
                snippet = json.dumps(snippet)[:2000]
            except Exception:
                snippet = str(snippet)[:2000]
            raise GenerationError(
                f"Response parser produced 0 files. Parsed response: {snippet}",
                upstream_body=parsed_json,
            )
        return out

    raise GenerationError(f"Unknown response_parser.type: {ptype!r}")


# --------------------------- test connectivity ---------------------------

async def test_config(module: str, config_id: int) -> dict[str, Any]:
    """Verify authentication without submitting a billable generation."""
    cfg = await load_config(module, config_id)
    if not cfg.api_key:
        return {"ok": False, "message": "API key is empty"}
    started = time.perf_counter()
    url = cfg.base_url.rstrip("/") + "/v1/models"
    try:
        await validate_outbound_url(url, allow_private=get_settings().allow_private_upstreams)
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {cfg.api_key}"})
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "message": f"Network error: {exc}",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except ValueError as exc:
        return {"ok": False, "message": str(exc), "latency_ms": 0}
    latency_ms = int((time.perf_counter() - started) * 1000)
    ok = resp.status_code == 200
    return {
        "ok": ok,
        "message": f"HTTP {resp.status_code}: {'auth accepted' if ok else resp.text[:300]}",
        "latency_ms": latency_ms,
        "http_status": resp.status_code,
    }
