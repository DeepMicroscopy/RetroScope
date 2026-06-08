"""Shared context for REST API route handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Request


@dataclass(slots=True)
class ApiContext:
    image_store: Any
    autofocus_svc: Any
    camera_svc: Any
    dispatcher: Any


def get_api_context(request: Request) -> ApiContext:
    return request.app.state.retroscope_api_context
