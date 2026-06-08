"""Shared context passed to each evaluation experiment."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from retroscope.evaluation.service_drive import MainThreadInvoker


@dataclass
class EvalContext:
    services: Any
    sangaboard: Any
    invoker: MainThreadInvoker
    out_dir: Path
    args: dict = field(default_factory=dict)

    @property
    def config(self):
        return self.services.config

    @property
    def camera_svc(self):
        return self.services.camera_svc

    @property
    def motion_ctrl(self):
        return self.services.motion_ctrl

    @property
    def objective_mgr(self):
        return self.services.objective_mgr

    @property
    def autofocus_svc(self):
        return self.services.autofocus_svc

    @property
    def focus_stacker_svc(self):
        return self.services.focus_stacker_svc

    @property
    def tile_scanner_svc(self):
        return self.services.tile_scanner_svc

    @property
    def image_store(self):
        return self.services.image_store

    def profile(self):
        return self.objective_mgr.current_profile()

    def um_per_pixel(self) -> float:
        return max(1e-6, float(self.profile().um_per_pixel))

    def backlash_xyz(self) -> tuple[int, int, int]:
        p = self.profile()
        return (int(p.backlash_x), int(p.backlash_y), int(p.backlash_z))

    def stage_um_per_step(self, axis: int) -> float:
        key = "motor.stage_um_per_step_y" if axis == 1 else "motor.stage_um_per_step_x"
        try:
            return float(self.config.get(key, 0.0))
        except Exception:
            return 0.0

    def arg(self, name: str, default: Any = None, cast=None):
        val = self.args.get(name, default)
        if cast is not None and val is not None:
            try:
                return cast(val)
            except (TypeError, ValueError):
                return default
        return val

    def arg_list_int(self, name: str, default: list[int]) -> list[int]:
        raw = self.args.get(name)
        if not raw:
            return list(default)
        try:
            return [int(x) for x in str(raw).split(",") if x.strip() != ""]
        except ValueError:
            return list(default)
