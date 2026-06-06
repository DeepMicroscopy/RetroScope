"""Tests for stage calibration math and bridge helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.bridge.calibration_bridge import CalibrationBridge
from retroscope.services.stage_calibration import stage_um_per_step, tile_steps_for_frame


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class FakeConfig:
    def __init__(self) -> None:
        self.values = {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value


class FakeObjectiveManager:
    def current_profile(self):
        return SimpleNamespace(
            backlash_x=0,
            backlash_y=0,
            backlash_z=0,
            um_per_pixel=1.0,
            focus_stack_step=5,
        )


def test_tile_step_uses_stage_calibration_when_available() -> None:
    step = tile_steps_for_frame(
        frame_width_px=1000,
        frame_height_px=500,
        um_per_pixel=0.5,
        overlap=0.2,
        stage_um_per_step_x=0.25,
        stage_um_per_step_y=0.5,
    )

    assert step.calibrated is True
    assert step.x_steps == 1600
    assert step.y_steps == 400


def test_tile_step_preserves_legacy_fallback_without_stage_calibration() -> None:
    step = tile_steps_for_frame(1280, 720, 1.0, 0.2, 0.0, 0.0)

    assert step.calibrated is False
    assert step.x_steps == 1024
    assert step.y_steps == 576


def test_tile_step_uses_each_axis_calibration_independently() -> None:
    step = tile_steps_for_frame(1000, 500, 0.5, 0.2, 0.25, 0.0)

    assert step.calibrated is True
    assert step.x_steps == 1600
    assert step.y_steps == 400


def test_stage_scale_from_camera_observed_move() -> None:
    assert stage_um_per_step(observed_pixels=250, um_per_pixel=0.5, motor_steps=5000) == pytest.approx(0.025)


def test_stage_axis_calibration_can_use_explicit_scale_snapshot() -> None:
    _app()
    cfg = FakeConfig()
    bridge = CalibrationBridge(None, None, FakeObjectiveManager(), cfg)

    assert bridge.setStageAxisCalibrationWithScale("y", 100, 170, 0.1331512797341311) is True

    assert cfg.values["motor.stage_um_per_step_y"] == pytest.approx(0.22635717554802287)
