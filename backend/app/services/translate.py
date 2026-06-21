"""Translation service.

Speaks the MiniMax chat-completions API directly (not via the
request_template / response_parser engine used by image/voice/music/
video — chat completions has a different shape). API key, base URL,
endpoint path and model are read from `api_configs` (module =
'translate') so users manage the key in one Config Center place.

Endpoint + structured-output contract:

  * Default endpoint: `/v1/text/chatcompletion_v2` (the
    platform-recommended path for M2.7 / M3 / M2.7-highspeed). It
    supports the `thinking: {type: "disabled"}` knob that suppresses
    reasoning from leaking into the `content` field (M2.7+ would
    otherwise emit a `<think>…</think>` block before the answer).
  * We always request `response_format: {type: "json_object"}` so the
    model's `content` is a strict JSON document with the shape:
        {"translation": "<text>", "detected_source": "<code>|null"}
    No cleaning / regex stripping needed on the way out — the model
    is the single source of truth, the wire format is the contract.
  * When the user has pinned the older OpenAI-compatible endpoint
    (`/v1/chat/completions`), we still send `response_format:
    json_object` but skip the `thinking` knob (older models don't
    know it). We then try to JSON-parse; if the model ignored the
    instruction and returned plain text, we fall back to using that
    text as the translation (and log a warning). That way the wire
    shape is reliable for the common case, and the legacy endpoint
    still works for old models.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import get_settings
from app.crypto import decrypt_str
from app.database import fetchrow
from app.security import validate_outbound_url

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """User-visible translation failure with a friendly message."""

    def __init__(
        self,
        message: str,
        *,
        http_status: Optional[int] = None,
        upstream_body: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.upstream_body = upstream_body


# ---------------------------------------------------------------------------
# Language catalogue
# ---------------------------------------------------------------------------
#
# `code` is what the UI sends. The model is told the full English name in
# the prompt (chat models understand "English" / "中文" equally well).
LANGUAGE_NAMES: dict[str, str] = {
    "auto": "auto-detect",
    "zh": "Simplified Chinese",
    "zh-TW": "Traditional Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "pt": "Portuguese",
    "it": "Italian",
    "ar": "Arabic",
}


# Map our internal language codes to ISO 639-1-ish codes the model is
# likely to emit when it identifies a source language. Empty string
# (the model returns it for "I don't know") maps to None upstream.
ISO_CODE_FOR: dict[str, str] = {
    "zh": "zh", "zh-TW": "zh-TW", "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es", "ru": "ru", "pt": "pt",
    "it": "it", "ar": "ar",
}


@dataclass
class TranslateResponse:
    translated_text: str
    source: str
    target: str
    model: str
    duration_ms: int
    detected_source: Optional[str] = None


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


@dataclass
class _ResolvedTranslateConfig:
    api_key: str
    base_url: str
    model: str
    endpoint_path: str  # e.g. "/v1/text/chatcompletion_v2"


async def _load_translate_config(config_id: Optional[int]) -> _ResolvedTranslateConfig:
    """Load the translate config. Falls back to the (only) enabled one
    when no config_id is given, mirroring the rest of the generator code.

    The API key lives on key_providers, so we resolve the key with the
    same auto-bind rules as the generator: zero → error, one → use it,
    many → ask the user to pick.
    """
    if config_id is not None:
        row = await fetchrow(
            "SELECT * FROM api_configs WHERE id = $1 AND module = $2",
            config_id,
            "translate",
        )
    else:
        row = await fetchrow(
            "SELECT * FROM api_configs WHERE module = $1 "
            "ORDER BY enabled DESC, id ASC LIMIT 1",
            "translate",
        )
    if not row:
        raise TranslationError(
            "No translate config found. Open Config Center → Translate and add one."
        )

    from app.database import fetch

    provider_id = row.get("key_provider_id")
    api_key = ""
    if provider_id is not None:
        prow = await fetchrow(
            "SELECT api_key_encrypted FROM key_providers WHERE id = $1",
            provider_id,
        )
        if prow and prow["api_key_encrypted"]:
            api_key = decrypt_str(prow["api_key_encrypted"])
    else:
        providers = await fetch(
            "SELECT id, api_key_encrypted FROM key_providers WHERE enabled = TRUE ORDER BY id ASC"
        )
        if not providers:
            raise TranslationError(
                "No API key configured. Open Config Center → API Keys and create one."
            )
        if len(providers) > 1:
            raise TranslationError(
                "Module 'translate' has no key_provider_id set and there are "
                f"{len(providers)} enabled providers. "
                "Edit the config and pick one explicitly."
            )
        api_key = decrypt_str(providers[0]["api_key_encrypted"]) if providers[0]["api_key_encrypted"] else ""

    return _ResolvedTranslateConfig(
        api_key=api_key,
        base_url=row["base_url"],
        model=row["model"],
        endpoint_path=row["endpoint_path"],
    )


# ---------------------------------------------------------------------------
# Prompt + structured output
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text from the "
    "source language to the target language. Preserve formatting (line "
    "breaks, lists, punctuation) and keep technical terms / proper nouns "
    "unchanged unless the target language has an established translation.\n\n"
    "Respond ONLY with a single JSON object — no prose, no Markdown fences, "
    "no commentary, no reasoning, no language tags. The shape is:\n"
    "  {\n"
    '    "translation": "<the translated text>",\n'
    '    "detected_source": "<ISO 639-1 code like en, zh, ja>"  '
    "OR null when the source was explicit (not auto)\n"
    "  }\n"
    "If the source is auto, fill detected_source with the code you "
    "detected. Otherwise detected_source must be null."
)


def _build_user_prompt(source: str, target: str, text: str) -> str:
    src_name = LANGUAGE_NAMES.get(source, source)
    tgt_name = LANGUAGE_NAMES.get(target, target)
    if source == "auto":
        return (
            f"Translate the following text into {tgt_name}. "
            f"Detect the source language automatically and put the code "
            f"in detected_source.\n\n"
            f"---\n{text}\n---"
        )
    return (
        f"Translate the following text from {src_name} to {tgt_name}.\n\n"
        f"---\n{text}\n---"
    )


def _is_v2_endpoint(endpoint_path: str) -> bool:
    """The v2 chat-completions endpoint (`/v1/text/chatcompletion_v2`) is
    the platform-recommended path for M2.7+ and accepts the `thinking`
    knob. The older OpenAI-compatible `/v1/chat/completions` endpoint
    doesn't know about it — sending the knob there yields a 400.
    """
    return "chatcompletion_v2" in endpoint_path


def _build_payload(
    model: str,
    messages: list[dict],
    endpoint_path: str,
) -> dict:
    """Build the upstream JSON body. v2 endpoints get the `thinking` knob
    and the strict json_object response format; legacy endpoints get
    json_object only.
    """
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    if _is_v2_endpoint(endpoint_path):
        payload["thinking"] = {"type": "disabled"}
    return payload


def _parse_response(data: dict, source: str) -> tuple[str, Optional[str]]:
    """Extract (translation, detected_source) from the upstream response.

    Primary path: the model returned JSON in `content` matching the
    schema we asked for. Fallback: the model ignored `response_format`
    and returned plain text (older endpoints / older models) — use the
    whole content as the translation and warn so the operator can
    upgrade their endpoint_path to v2.
    """
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        snippet = json.dumps(data)[:1000] if isinstance(data, (dict, list)) else str(data)[:1000]
        raise TranslationError(
            f"Unexpected response shape: missing choices[0].message.content. "
            f"Snippet: {snippet}"
        ) from exc

    if not isinstance(content, str):
        raise TranslationError(
            f"Unexpected content type: {type(content).__name__}. "
            f"Snippet: {str(content)[:200]}"
        )

    # Primary: parse JSON and pull out the two fields.
    try:
        j = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(
            "Upstream returned non-JSON content despite response_format=json_object. "
            "Falling back to raw text. Consider switching endpoint_path to "
            "/v1/text/chatcompletion_v2 if the model supports it. "
            "First 200 chars: %r", content[:200],
        )
        return content.strip(), None

    if not isinstance(j, dict):
        logger.warning("Upstream JSON was not an object: %r — using raw content", j)
        return content.strip(), None

    translation = j.get("translation")
    if not isinstance(translation, str) or not translation.strip():
        # Sometimes the model returns the answer under a different key
        # (rare, but `text` / `result` / `output` show up in the wild).
        for alt in ("text", "result", "output", "answer"):
            v = j.get(alt)
            if isinstance(v, str) and v.strip():
                translation = v
                break
    if not isinstance(translation, str) or not translation.strip():
        raise TranslationError(
            f"Model response is missing the 'translation' field. "
            f"Got: {str(j)[:300]}"
        )

    detected_raw = j.get("detected_source")
    detected: Optional[str] = None
    if source == "auto" and isinstance(detected_raw, str) and detected_raw.strip():
        norm = detected_raw.strip().lower()
        # The model may emit a friendly name ("English", "中文") or a code.
        # Normalise to a code we know; if we can't, drop it on the floor
        # rather than leaking the raw string into the UI.
        if norm in ISO_CODE_FOR:
            detected = ISO_CODE_FOR[norm]
        else:
            for code, friendly in LANGUAGE_NAMES.items():
                if norm == friendly.lower():
                    detected = code
                    break

    return translation.strip(), detected


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_translation(
    text: str,
    source: str,
    target: str,
    config_id: Optional[int] = None,
    model: Optional[str] = None,
) -> TranslateResponse:
    """Translate `text` from `source` to `target` via the MiniMax chat API.

    `source` may be 'auto' (the model detects). `target` must be a known
    code from LANGUAGE_NAMES. `model`, if supplied, overrides the model
    on the resolved config row. Raises TranslationError on any failure.
    """
    if not text or not text.strip():
        raise TranslationError("Source text is empty")
    if target not in LANGUAGE_NAMES or target == "auto":
        raise TranslationError(f"Unsupported target language: {target!r}")
    if source not in LANGUAGE_NAMES:
        raise TranslationError(f"Unsupported source language: {source!r}")
    if source != "auto" and source == target:
        raise TranslationError("Source and target languages are the same")

    cfg = await _load_translate_config(config_id)
    if not cfg.api_key:
        raise TranslationError(
            "API key is empty. Open Config Center → Translate and paste your key."
        )

    # Per-call model override wins over the config's model. Whitespace-only
    # strings fall back to the config (treat them as "empty").
    effective_model = (model.strip() if model else "") or cfg.model

    url = cfg.base_url.rstrip("/") + "/" + cfg.endpoint_path.lstrip("/")
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(
        effective_model,
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(source, target, text)},
        ],
        cfg.endpoint_path,
    )

    settings = get_settings()
    try:
        await validate_outbound_url(url, allow_private=settings.allow_private_upstreams)
    except ValueError as exc:
        raise TranslationError(str(exc)) from exc
    timeout = httpx.Timeout(settings.request_timeout, connect=30.0)
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise TranslationError(f"Network error talking to MiniMax: {exc}") from exc

    if resp.status_code >= 400:
        # Surface a useful error message
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:1000]
        msg = f"HTTP {resp.status_code}"
        if isinstance(body, dict):
            for key in ("error", "message", "detail"):
                if key in body and isinstance(body[key], (str, dict)):
                    val = body[key]
                    if isinstance(val, dict) and "message" in val:
                        msg += f": {val['message']}"
                    else:
                        msg += f": {val}"
                    break
        else:
            msg += f": {body}"
        raise TranslationError(msg[:1500], http_status=resp.status_code, upstream_body=str(body)[:1500])

    try:
        data = resp.json()
    except Exception as exc:
        raise TranslationError(f"Upstream returned non-JSON response: {exc}") from exc

    translation, detected = _parse_response(data, source)
    if not translation:
        raise TranslationError("Model returned an empty translation")

    duration_ms = int((time.perf_counter() - started) * 1000)
    return TranslateResponse(
        translated_text=translation,
        source=source,
        target=target,
        model=effective_model,
        duration_ms=duration_ms,
        detected_source=detected,
    )
