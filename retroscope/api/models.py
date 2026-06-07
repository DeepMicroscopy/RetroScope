"""Pydantic models for the REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    app: str = "retroscope"


class CapturePosition(BaseModel):
    x: int | None = None
    y: int | None = None
    z: int | None = None


class CaptureSummary(BaseModel):
    id: str
    filename: str
    type: str
    captured_at: str
    objective: str
    width: int
    height: int
    file_size: int
    format: str
    tags: list[str] = Field(default_factory=list)
    position: CapturePosition
    metadata: dict[str, Any] = Field(default_factory=dict)
    download_url: str


class CaptureListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    captures: list[CaptureSummary]


class ActionResponse(BaseModel):
    action: str
    state: str
    busy: bool
    cancelling: bool = False
    message: str = ""
