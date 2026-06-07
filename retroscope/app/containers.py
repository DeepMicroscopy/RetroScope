"""Containers used by the application root."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Drivers:
    sangaboard: Any
    ads: Any
    encoder: Any
    endstop: Any
    buttons: Any


@dataclass(slots=True)
class Services:
    config: Any
    objective_mgr: Any
    motion_ctrl: Any
    image_store: Any
    camera_svc: Any
    input_mgr: Any
    button_mgr: Any
    update_svc: Any
    system_svc: Any
    autofocus_svc: Any
    objective_detector: Any
    measurement_capture_svc: Any
    storage_svc: Any
    rest_api_svc: Any | None = None
    focus_stacker_svc: Any | None = None
    tile_scanner_svc: Any | None = None


@dataclass(slots=True)
class Bridges:
    motion: Any
    objective: Any
    overlay: Any
    gallery: Any
    status: Any
    update: Any
    system: Any
    buttons: Any
    autofocus: Any
    measurement: Any
    automation: Any
    calibration: Any
    settings: Any
    obj_detector: Any


@dataclass(slots=True)
class ImageProviders:
    camera: Any
    ome: Any
