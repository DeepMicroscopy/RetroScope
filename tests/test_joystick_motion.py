"""Test the joystick motion smoothing and command dispatch logic."""

from __future__ import annotations

import queue
import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.drivers.sangaboard import MockSangaboard, SangaboardDriver
from retroscope.services.motion_controller import MotionController, joystick_dispatch_params


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


def test_joystick_dispatch_uses_fixed_low_latency_parameters() -> None:
    params = joystick_dispatch_params()

    assert params.interval_ms == 25
    assert params.min_command_steps == 1
    assert params.force_command_ms == 50
    assert params.target_alpha == pytest.approx(0.90)


def test_joystick_target_smoothing_reduces_abrupt_jumps() -> None:
    ctrl, _ = _controller()

    first = ctrl._smooth_joystick_target(0.0, 1.0, active=True, sign_changed=False)
    second = ctrl._smooth_joystick_target(first, 1.0, active=True, sign_changed=False)
    reversed_target = ctrl._smooth_joystick_target(second, -1.0, active=True, sign_changed=True)

    assert 0.0 < first < 1.0
    assert first < second < 1.0
    assert reversed_target < 0.0


def test_low_speed_joystick_emits_small_frequent_commands() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    params = joystick_dispatch_params()
    now = time.monotonic()

    ctrl.on_axes_updated(4096, 0)
    for i in range(12):
        ctrl._dispatch_joystick_at(now + i * params.interval_s)

    sizes = [abs(dx) for dx, _dy, _dz, _coalesce in sb.moves]
    assert sizes
    assert max(sizes) <= 2


def test_ads_updates_do_not_move_until_dispatch() -> None:
    ctrl, sb = _controller()

    ctrl.on_axes_updated(12000, 0)
    ctrl.on_axes_updated(12000, 0)

    assert sb.moves == []
    ctrl._dispatch_joystick_at(time.monotonic())
    assert len(sb.moves) == 1


def test_dispatch_sends_small_commands_without_batching() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    now = time.monotonic()
    params = joystick_dispatch_params()

    ctrl.on_axes_updated(4096, 0)
    for i in range(4):
        ctrl.on_axes_updated(4096, 0)
        ctrl._joystick_sample_t = now + i * params.interval_s
        ctrl._dispatch_joystick_at(now + i * params.interval_s)

    sizes = [abs(dx) for dx, _dy, _dz, _coalesce in sb.moves]
    assert sizes
    assert max(sizes) <= 2


def test_tiny_deflection_emits_low_amplitude_commands() -> None:
    ctrl, sb = _controller(_Config(**{"input.max_pan_speed_px_per_sec": 10}))
    now = time.monotonic()
    params = joystick_dispatch_params()

    for i in range(8):
        ctrl.on_axes_updated(1000, 0)
        ctrl._joystick_sample_t = now + i * params.interval_s
        ctrl._dispatch_joystick_at(now + i * params.interval_s)

    sizes = [abs(dx) for dx, _dy, _dz, _coalesce in sb.moves]
    assert sizes
    assert max(sizes) <= 1


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
    assert sb.moves

    sb.moves.clear()
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
    assert sb.moves

    ctrl.on_axes_updated(-4096, 0)
    ctrl._dispatch_joystick_at(now + 0.067)

    assert sb.moves[-1][0] < 0
    assert ctrl._dx_accum <= 0.0


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
