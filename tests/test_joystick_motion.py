"""Test the joystick motion smoothing and command dispatch logic."""

from __future__ import annotations

import queue
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.drivers.sangaboard import MockSangaboard, SangaboardDriver
from retroscope.services.motion_controller import MotionController, joystick_smoothing_params


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class _Config:
    def __init__(self, **overrides) -> None:
        self._data = {
            "input.max_pan_speed_px_per_sec": 400,
            "input.curve": "linear",
            "motor.stage_um_per_step_x": 1.0,
            "motor.stage_um_per_step_y": 1.0,
            **overrides,
        }

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value


class _ObjectiveManager:
    active_objective = "4x"

    def current_profile(self):
        return SimpleNamespace(
            name="4x",
            display_name="4x",
            backlash_x=0,
            backlash_y=0,
            backlash_z=0,
            um_per_pixel=1.0,
            focus_stack_step=10,
        )


class _Sangaboard:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int, bool]] = []

    def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
        self.moves.append((dx, dy, dz, coalesce))


def _controller(config: _Config | None = None) -> tuple[MotionController, _Sangaboard]:
    _app()
    sb = _Sangaboard()
    ctrl = MotionController(sb, _ObjectiveManager(), config or _Config())
    ctrl._set_joystick_center(0.0, 0.0)
    return ctrl, sb


def test_joystick_smoothing_parameter_mapping() -> None:
    responsive = joystick_smoothing_params(0)
    default = joystick_smoothing_params(25)
    quiet = joystick_smoothing_params(100)

    assert responsive.interval_ms == 40
    assert responsive.min_command_steps == 4
    assert responsive.force_command_ms == 120
    assert responsive.target_alpha == pytest.approx(0.90)
    assert default.interval_ms == 52
    assert default.min_command_steps == 6
    assert default.force_command_ms == 170
    assert quiet.interval_ms == 90
    assert quiet.min_command_steps == 12
    assert quiet.force_command_ms == 320
    assert quiet.target_alpha == pytest.approx(0.40)


def test_joystick_target_smoothing_reduces_abrupt_jumps() -> None:
    ctrl, _ = _controller()
    ctrl.setJoystickSmoothingPct(100)

    first = ctrl._smooth_joystick_target(0.0, 1.0, active=True, sign_changed=False)
    second = ctrl._smooth_joystick_target(first, 1.0, active=True, sign_changed=False)
    reversed_target = ctrl._smooth_joystick_target(second, -1.0, active=True, sign_changed=True)

    assert 0.0 < first < 1.0
    assert first < second < 1.0
    assert reversed_target < 0.0


def test_responsive_smoothing_emits_more_smaller_commands_than_quiet() -> None:
    responsive_ctrl, responsive_sb = _controller(_Config(**{"input.joystick_smoothing_pct": 0}))
    quiet_ctrl, quiet_sb = _controller(_Config(**{"input.joystick_smoothing_pct": 100}))
    responsive_params = joystick_smoothing_params(0)
    quiet_params = joystick_smoothing_params(100)
    now = time.monotonic()

    responsive_ctrl.on_axes_updated(4096, 0)
    quiet_ctrl.on_axes_updated(4096, 0)
    for i in range(25):
        responsive_ctrl._dispatch_joystick_at(now + i * responsive_params.interval_s)
    for i in range(12):
        quiet_ctrl._dispatch_joystick_at(now + i * quiet_params.interval_s)

    responsive_sizes = [abs(dx) for dx, _dy, _dz, _coalesce in responsive_sb.moves]
    quiet_sizes = [abs(dx) for dx, _dy, _dz, _coalesce in quiet_sb.moves]
    assert len(responsive_sizes) > len(quiet_sizes)
    assert sum(responsive_sizes) / len(responsive_sizes) < sum(quiet_sizes) / len(quiet_sizes)


def test_ads_updates_do_not_move_until_dispatch() -> None:
    ctrl, sb = _controller()

    ctrl.on_axes_updated(12000, 0)
    ctrl.on_axes_updated(12000, 0)

    assert sb.moves == []
    ctrl._dispatch_joystick_at(time.monotonic())
    assert len(sb.moves) == 1


def test_dispatch_accumulates_before_sending_small_commands() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    now = time.monotonic()

    ctrl.on_axes_updated(4096, 0)
    ctrl._dispatch_joystick_at(now)
    ctrl._dispatch_joystick_at(now + 0.067)
    assert sb.moves == []

    ctrl._dispatch_joystick_at(now + 0.134)
    assert len(sb.moves) == 1
    assert abs(sb.moves[-1][0]) >= 6


def test_dispatch_forces_small_command_after_hold_time() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    now = time.monotonic()

    ctrl.on_axes_updated(1000, 0)
    ctrl._dispatch_joystick_at(now)
    ctrl.on_axes_updated(1000, 0)
    ctrl._joystick_sample_t = now + 0.24
    ctrl._dispatch_joystick_at(now + 0.24)
    assert sb.moves == []

    ctrl.on_axes_updated(1000, 0)
    ctrl._joystick_sample_t = now + 0.50
    ctrl._dispatch_joystick_at(now + 0.50)
    assert len(sb.moves) == 1
    assert 1 <= abs(sb.moves[-1][0]) < 6


def test_rest_noise_below_deadzone_emits_no_movement() -> None:
    ctrl, sb = _controller()
    ctrl.setDeadzone(0.10)
    now = time.monotonic()

    for i in range(6):
        ctrl.on_axes_updated(700, -700)
        ctrl._dispatch_joystick_at(now + i * 0.067)

    assert sb.moves == []


def test_hysteresis_exits_and_clears_accumulator_below_release_band() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    ctrl.setDeadzone(0.10)
    now = time.monotonic()

    ctrl.on_axes_updated(4096, 0)
    ctrl._dispatch_joystick_at(now)
    assert ctrl._dx_accum > 0.0

    ctrl.on_axes_updated(500, 0)
    ctrl._dispatch_joystick_at(now + 0.067)

    assert sb.moves == []
    assert ctrl._dx_accum == 0.0


def test_stale_joystick_sample_clears_motion_state_quickly() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 400}))
    now = time.monotonic()

    ctrl.on_axes_updated(12000, 0)
    ctrl._dispatch_joystick_at(now)
    assert sb.moves

    sb.moves.clear()
    ctrl._dispatch_joystick_at(now + 0.20)

    assert sb.moves == []
    assert ctrl._joystick_sample_ready is False
    assert ctrl._vx_filtered == 0.0
    assert ctrl._dx_accum == 0.0


def test_sign_change_clears_stale_accumulator() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    now = time.monotonic()

    ctrl.on_axes_updated(4096, 0)
    ctrl._dispatch_joystick_at(now)
    assert ctrl._dx_accum > 0.0

    ctrl.on_axes_updated(-4096, 0)
    ctrl._dispatch_joystick_at(now + 0.067)

    assert sb.moves == []
    assert ctrl._dx_accum < 0.0


def test_sangaboard_coalesce_preserves_non_move_commands_and_drops_pending_moves() -> None:
    driver = SangaboardDriver()
    driver._queue.put_nowait(("zero",))
    driver.move_rel(1, 0, 0, coalesce=False)
    driver.move_rel(2, 0, 0, coalesce=False)
    driver.move_rel(9, 0, 0, coalesce=True)

    queued = []
    try:
        while True:
            queued.append(driver._queue.get_nowait())
    except queue.Empty:
        pass

    assert queued == [("zero",), ("move", 9, 0, 0)]


def test_sangaboard_timing_commands_are_queued() -> None:
    driver = SangaboardDriver()

    driver.request_motion_timing()
    driver.set_step_time_us(750)
    driver.set_ramp_time_us(25000)

    queued = [driver._queue.get_nowait() for _ in range(3)]
    assert queued == [
        ("read_motion_timing",),
        ("set_step_time", 750),
        ("set_ramp_time", 25000),
    ]


def test_mock_sangaboard_reports_board_timing() -> None:
    _app()
    mock = MockSangaboard()
    seen: list[tuple[int, int]] = []
    mock.motion_timing_updated.connect(lambda step, ramp: seen.append((step, ramp)))

    mock.request_motion_timing()
    mock.set_step_time_us(800)
    mock.set_ramp_time_us(20000)

    assert seen == [(1000, 0), (800, 0), (800, 20000)]
