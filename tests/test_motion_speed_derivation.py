"""Verify joystick pan speed derives correctly from axis + objective calibration.

Formula: motor_steps_per_sec = max_pan_speed_px_per_sec * um_per_pixel / stage_um_per_step_axis * command_boost.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication

from retroscope.services.motion_controller import (
    JoystickAxisNormalizer,
    MotionController,
    _JOYSTICK_PAN_COMMAND_BOOST,
)


class _Cfg:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value


class _Obj:
    def __init__(self, um_per_pixel: float) -> None:
        self._upp = um_per_pixel

    def current_profile(self):
        return SimpleNamespace(um_per_pixel=self._upp)


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _ctrl(um_per_pixel: float, **cfg_kw) -> MotionController:
    _app()
    return MotionController(
        sangaboard=SimpleNamespace(),
        objective_manager=_Obj(um_per_pixel),
        config=_Cfg({**cfg_kw}),
    )


def test_pan_speed_scales_with_um_per_pixel_at_constant_stage_calibration():
    """At 4x (2.5 µm/px) vs 100x (0.1 µm/px), same stage, same px/s -> 25× steps/s ratio."""
    fast = _ctrl(
        um_per_pixel=2.5,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 1.0, "motor.stage_um_per_step_y": 1.0},
    )
    slow = _ctrl(
        um_per_pixel=0.1,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 1.0, "motor.stage_um_per_step_y": 1.0},
    )
    fast_sps, fast_y_sps = fast._derived_pan_steps_per_second_xy(fast._obj.current_profile())
    slow_sps, slow_y_sps = slow._derived_pan_steps_per_second_xy(slow._obj.current_profile())
    assert fast_sps == pytest.approx(1000.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert fast_y_sps == pytest.approx(fast_sps)
    assert slow_sps == pytest.approx(40.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert slow_y_sps == pytest.approx(slow_sps)
    assert fast_sps / slow_sps == pytest.approx(25.0)


def test_pan_speed_inverse_with_stage_step_size():
    """Finer stage (smaller µm/step) -> more motor steps per second for the same on-screen velocity."""
    coarse = _ctrl(
        um_per_pixel=1.0,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 1.0, "motor.stage_um_per_step_y": 1.0},
    )
    fine = _ctrl(
        um_per_pixel=1.0,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 0.1, "motor.stage_um_per_step_y": 0.1},
    )
    coarse_sps, coarse_y_sps = coarse._derived_pan_steps_per_second_xy(coarse._obj.current_profile())
    fine_sps, fine_y_sps = fine._derived_pan_steps_per_second_xy(fine._obj.current_profile())
    assert coarse_sps == pytest.approx(400.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert coarse_y_sps == pytest.approx(coarse_sps)
    assert fine_sps == pytest.approx(4000.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert fine_y_sps == pytest.approx(fine_sps)


def test_uncalibrated_stage_falls_back_to_one_um_per_step():
    """With both stage X/Y set to 0.0, the fallback (1.0) keeps the joystick usable."""
    ctrl = _ctrl(
        um_per_pixel=2.0,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 0.0, "motor.stage_um_per_step_y": 0.0},
    )
    x_sps, y_sps = ctrl._derived_pan_steps_per_second_xy(ctrl._obj.current_profile())
    assert x_sps == pytest.approx(800.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert y_sps == pytest.approx(800.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert ctrl._stage_um_per_step("x") == pytest.approx(1.0)
    assert ctrl._stage_um_per_step("y") == pytest.approx(1.0)


def test_one_axis_calibrated_uses_that_value():
    """When only X is set (e.g. Y still 0), the uncalibrated axis falls back to X."""
    ctrl = _ctrl(
        um_per_pixel=1.0,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 0.5, "motor.stage_um_per_step_y": 0.0},
    )
    assert ctrl._stage_um_per_step("x") == pytest.approx(0.5)
    assert ctrl._stage_um_per_step("y") == pytest.approx(0.5)


def test_pan_speed_uses_axis_specific_stage_calibration():
    ctrl = _ctrl(
        um_per_pixel=1.5,
        **{"input.max_pan_speed_px_per_sec": 400, "motor.stage_um_per_step_x": 1.0, "motor.stage_um_per_step_y": 3.0},
    )

    x_sps, y_sps = ctrl._derived_pan_steps_per_second_xy(ctrl._obj.current_profile())

    assert x_sps == pytest.approx(600.0 * _JOYSTICK_PAN_COMMAND_BOOST)
    assert y_sps == pytest.approx(200.0 * _JOYSTICK_PAN_COMMAND_BOOST)


def test_joystick_normalizer_is_responsive_before_full_span_is_seen():
    norm = JoystickAxisNormalizer()
    norm.set_center(12000)

    assert norm.normalize(15000) > 0.3
