"""Pydantic v2 request / response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ModuleName = Literal["image", "voice", "music", "video"]
StatusName = Literal["pending", "running", "success", "failed"]


# -------------------- key_providers --------------------
#
# API keys live in their own table, decoupled from the per-module config
# rows. A config references one provider via `key_provider_id`; if it
# leaves that NULL and there's exactly one enabled provider, the generator
# binds to it automatically.

class KeyProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    enabled: bool = True


class KeyProviderCreate(KeyProviderBase):
    api_key: str = ""  # plaintext on the wire; encrypted before storage


class KeyProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    api_key: Optional[str] = None  # empty string clears the key
    enabled: Optional[bool] = None


class KeyProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    has_api_key: bool  # never echo the encrypted blob
    enabled: bool
    created_at: datetime
    updated_at: datetime


class KeyProviderTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int = 0
    http_status: Optional[int] = None
    sample_response: Optional[Any] = None


# -------------------- api_configs --------------------

class ConfigBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    # `key_provider_id` is the only key-related field on a config now. Leave
    # it null and the runtime will auto-bind to the only enabled provider
    # (the common single-key case). When more than one provider exists,
    # null is treated as "ambiguous" and the request is rejected with a
    # hint to pick one explicitly.
    key_provider_id: Optional[int] = None
    base_url: str
    endpoint_path: str
    model: str = ""
    request_template: dict[str, Any]
    response_parser: dict[str, Any]
    default_params: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ConfigCreate(ConfigBase):
    # `module` is a free-form string. The well-known values (image/voice/music/video)
    # get a 4-row default seed and a dedicated tab in the UI. Other values (e.g.
    # "smoke_image" for test isolation) are still allowed — they're just less ergonomic.
    module: str = Field(min_length=1, max_length=50)


class ConfigUpdate(BaseModel):
    display_name: Optional[str] = None
    key_provider_id: Optional[int] = None
    base_url: Optional[str] = None
    endpoint_path: Optional[str] = None
    model: Optional[str] = None
    request_template: Optional[dict[str, Any]] = None
    response_parser: Optional[dict[str, Any]] = None
    default_params: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    # Free-form — see note on ConfigCreate.module
    module: str
    display_name: str
    # Denormalised: the joined-in provider's id / name / key-present flag.
    # has_api_key is computed at response time so it always reflects the
    # current state of the linked provider (e.g. key cleared elsewhere).
    key_provider_id: Optional[int] = None
    key_provider_name: Optional[str] = None
    has_api_key: bool  # resolved from the linked provider
    base_url: str
    endpoint_path: str
    model: str
    request_template: dict[str, Any]
    response_parser: dict[str, Any]
    default_params: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ConfigTestResult(BaseModel):
    ok: bool
    message: str
    latency_ms: int = 0
    http_status: Optional[int] = None
    sample_response: Optional[Any] = None


# -------------------- generation --------------------

class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    params: dict[str, Any] = Field(default_factory=dict)
    config_id: Optional[int] = None  # default: the enabled config for that module


class OutputFile(BaseModel):
    type: str            # "image" / "audio" / "video"
    url: str             # served via /api/media/...
    size: int = 0
    mime_type: str = ""
    path: str            # absolute file path on disk
    source_url: Optional[str] = None  # original URL returned by the upstream API


class GenerateResult(BaseModel):
    id: int
    module: ModuleName
    status: StatusName
    prompt: str
    params: dict[str, Any]
    output_files: list[OutputFile] = Field(default_factory=list)
    error_message: str = ""
    duration_ms: int = 0
    created_at: datetime


# -------------------- history --------------------

class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    # Free-form — same rationale as ConfigOut.module
    module: str
    config_id: int | None
    prompt: str
    status: StatusName
    output_files: list[OutputFile]
    error_message: str
    duration_ms: int
    created_at: datetime


class HistoryDetail(HistoryItem):
    params: dict[str, Any]
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]


# -------------------- secrets --------------------

class SecretMeta(BaseModel):
    name: str
    description: str = ""
    has_value: bool
    created_at: datetime
    updated_at: datetime


class SecretUpsert(BaseModel):
    value: str
    description: str = ""
