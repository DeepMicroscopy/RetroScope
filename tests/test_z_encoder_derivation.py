"""Verify one encoder click moves X motor steps."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication

from retroscope.services.motion_controller import (
    ENCODER_TRIGGER_UNITS,
    MotionController,
)


class _Cfg:
    def __init__(self, data: dict | None = None) -> None:
        self._data = data or {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value


class _Obj:
    def __init__(self, focus_stack_step: int) -> None:
        self._step = focus_stack_step

    def current_profile(self):
        return SimpleNamespace(
            focus_stack_step=self._step,
            backlash_x=0,
            backlash_y=0,
            backlash_z=0,
        )


class _Sangaboard:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int]] = []

    def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
        self.moves.append((dx, dy, dz))

    def stop_motors(self) -> None:
        pass


def _app():
    return QCoreApplication.instance() or QCoreApplication([])


def _ctrl(focus_stack_step: int, multiplier: float) -> tuple[MotionController, _Sangaboard]:
    _app()
    sb = _Sangaboard()
    ctrl = MotionController(
        sangaboard=sb,
        objective_manager=_Obj(focus_stack_step),
        config=_Cfg({"input.z_encoder_step_multiplier": multiplier}),
    )
    return ctrl, sb


def test_one_click_at_unit_multiplier_moves_focus_stack_step():
    ctrl, sb = _ctrl(focus_stack_step=20, multiplier=1.0)
    ctrl.on_encoder_stepped(ENCODER_TRIGGER_UNITS)
    assert sb.moves == [(0, 0, 20)]


def test_two_times_multiplier_doubles_step_size():
    ctrl, sb = _ctrl(focus_stack_step=2, multiplier=2.0)
    ctrl.on_encoder_stepped(ENCODER_TRIGGER_UNITS)
    assert sb.moves == [(0, 0, 4)]


def test_minimum_one_step_even_when_focus_step_is_one_and_multiplier_below_one():
    """100x has focus_stack_step=1, a 0.5× multiplier rounds down but the floor is 1."""
    ctrl, sb = _ctrl(focus_stack_step=1, multiplier=0.5)
    ctrl.on_encoder_stepped(ENCODER_TRIGGER_UNITS)
    assert sb.moves == [(0, 0, 1)]


def test_negative_encoder_delta_moves_z_negative():
    ctrl, sb = _ctrl(focus_stack_step=5, multiplier=1.0)
    ctrl.on_encoder_stepped(-ENCODER_TRIGGER_UNITS)
    assert sb.moves == [(0, 0, -5)]


def test_multiple_triggers_accumulate_steps():
    ctrl, sb = _ctrl(focus_stack_step=10, multiplier=1.0)
    ctrl.on_encoder_stepped(2 * ENCODER_TRIGGER_UNITS)
    assert sb.moves == [(0, 0, 10), (0, 0, 10)]
