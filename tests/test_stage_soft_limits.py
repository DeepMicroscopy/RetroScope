"""Tests for stage soft limit behavior in MotionController and TileScannerWorker.

Note: Partially AI-generated
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.services.motion_controller import MotionController


class FakeConfig:
    def __init__(self, soft_limits: dict | None = None) -> None:
        self._data = {
            "motor": {
                "soft_limits": {
                    "enabled": False,
                    "calibrated": False,
                    "x_min": 0,
                    "x_max": 0,
                    "y_min": 0,
                    "y_max": 0,
                    **(soft_limits or {}),
                }
            }
        }
        self.save_count = 0

    def get(self, key: str, default=None):
        node = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value) -> None:
        node = self._data
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def save(self) -> None:
        self.save_count += 1


class FakeObjectiveManager:
    active_objective = "10x"

    def current_profile(self):
        return SimpleNamespace(
            backlash_x=0,
            backlash_y=0,
            backlash_z=0,
            um_per_pixel=1.0,
            focus_stack_step=10,
        )


class FakeSangaboard:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int]] = []
        self.blocking_moves: list[tuple[int, int, int, float | None]] = []
        self.zeroed = False
        self.stopped = False
        self.released = False

    def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
        self.moves.append((dx, dy, dz))

    def move_rel_blocking(self, dx: int, dy: int, dz: int, timeout: float | None = None) -> bool:
        self.blocking_moves.append((dx, dy, dz, timeout))
        return True

    def zero_position(self) -> None:
        self.zeroed = True

    def stop_motors(self) -> None:
        self.stopped = True

    def release_motors(self) -> None:
        self.released = True


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _controller(config: FakeConfig | None = None) -> tuple[MotionController, FakeSangaboard]:
    _app()
    sb = FakeSangaboard()
    ctrl = MotionController(sb, FakeObjectiveManager(), config or FakeConfig())
    return ctrl, sb


def test_home_zero_requires_endstop_and_resets_soft_limit_state() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_max": 100, "y_max": 100})
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    resets: list[tuple[int, int, int]] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.position_reset.connect(lambda x, y, z: resets.append((x, y, z)))
    ctrl.on_position_updated(50, 60, 70)

    assert ctrl.confirm_home_zero() is False
    assert blocked[-1] == "stage_home_requires_endstop"
    assert sb.zeroed is False

    ctrl.on_endstop_triggered(True)

    assert ctrl.confirm_home_zero() is True
    assert sb.zeroed is True
    assert resets[-1] == (0, 0, 0)
    assert ctrl.soft_limits_enabled is False
    assert ctrl.soft_limits_calibrated is False
    assert cfg.get("motor.soft_limits.enabled") is False
    assert cfg.save_count >= 1


def test_bottom_right_limit_normalizes_and_persists() -> None:
    cfg = FakeConfig()
    ctrl, _ = _controller(cfg)
    ctrl.on_position_updated(-500, 300, 0)

    assert ctrl.save_bottom_right_limit() is True

    assert ctrl.soft_limits_enabled is True
    assert ctrl.soft_limits_calibrated is True
    assert (ctrl.soft_limit_x_min, ctrl.soft_limit_x_max) == (-500, 0)
    assert (ctrl.soft_limit_y_min, ctrl.soft_limit_y_max) == (0, 300)
    assert cfg.get("motor.soft_limits.x_min") == -500
    assert cfg.get("motor.soft_limits.y_max") == 300


def test_motion_controller_blocks_out_of_range_move() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100})
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.on_position_updated(50, 50, 0)

    assert ctrl.move_rel(20, 0, 0) is True
    assert sb.moves[-1] == (20, 0, 0)
    assert ctrl.move_rel(40, 0, 0) is False

    assert sb.moves == [(20, 0, 0)]
    assert blocked[-1] == "soft_limit_stage"

def test_blocking_z_move_uses_blocking_driver_without_touching_live_queue() -> None:
    ctrl, sb = _controller()

    assert ctrl.move_z_blocking(123) is True

    assert sb.moves == []
    assert len(sb.blocking_moves) == 1
    dx, dy, dz, timeout = sb.blocking_moves[0]
    assert (dx, dy, dz) == (0, 0, 123)
    assert timeout is not None and timeout >= 5.0


def test_normal_z_move_stays_fire_and_forget() -> None:
    ctrl, sb = _controller()

    assert ctrl.move_z(123) is True

    assert sb.moves == [(0, 0, 123)]
    assert sb.blocking_moves == []


def test_deenergize_motors_releases_hold_and_clears_intent() -> None:
    ctrl, sb = _controller()
    ctrl._vx_filtered = 0.5
    ctrl._vy_filtered = -0.5
    ctrl._dx_accum = 1.2
    ctrl._dy_accum = -2.4
    ctrl._encoder_accum = 75

    ctrl.deenergize_motors()

    assert sb.released is True
    assert ctrl._vx_filtered == 0.0
    assert ctrl._vy_filtered == 0.0
    assert ctrl._dx_accum == 0.0
    assert ctrl._dy_accum == 0.0
    assert ctrl._encoder_accum == 0


def test_joystick_move_is_blocked_at_soft_limit() -> None:
    cfg = FakeConfig({"enabled": True, "calibrated": True, "x_min": 0, "x_max": 100, "y_min": 0, "y_max": 100})
    cfg.set("motor.stage_um_per_step_x", 0.001)
    cfg.set("motor.stage_um_per_step_y", 0.001)
    ctrl, sb = _controller(cfg)
    blocked: list[str] = []
    ctrl.motion_blocked.connect(blocked.append)
    ctrl.on_position_updated(99, 50, 0)
    ctrl._center_x = 0
    ctrl._center_y = 0

    ctrl.on_axes_updated(32767, 0)
    ctrl._dispatch_joystick_at(time.monotonic())

    assert sb.moves == []
    assert blocked[-1] == "soft_limit_stage"
