"""Pydantic v2 request / response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ModuleName = Literal["image", "voice", "music", "video"]
StatusName = Literal["pending", "running", "success", "failed"]


# -------------------- api_configs --------------------

class ConfigBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    api_key: str = ""  # plaintext on the wire; encrypted before storage
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
    api_key: Optional[str] = None
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
    base_url: str
    endpoint_path: str
    model: str
    request_template: dict[str, Any]
    response_parser: dict[str, Any]
    default_params: dict[str, Any]
    enabled: bool
    has_api_key: bool  # never echo the encrypted blob
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
    prompt: str = Field(min_length=1)
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
