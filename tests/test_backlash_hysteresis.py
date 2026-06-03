"""Tests for the per-axis hysteresis-band slack model in MotionController.

Note: Partially AI-generated
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.services.motion_controller import MotionController
from tests.test_stage_soft_limits import FakeConfig, FakeSangaboard


class ObjMgr:
    """Objective manager stub with mutable per-axis backlash."""

    def __init__(self, backlash_x: int = 100, backlash_y: int = 100, backlash_z: int = 60) -> None:
        self._bx = int(backlash_x)
        self._by = int(backlash_y)
        self._bz = int(backlash_z)

    def current_profile(self):
        return SimpleNamespace(
            backlash_x=self._bx,
            backlash_y=self._by,
            backlash_z=self._bz,
            um_per_pixel=1.0,
            focus_stack_step=10,
        )


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def _ctrl(backlash_x: int = 100, backlash_y: int = 100, backlash_z: int = 60) -> tuple[MotionController, FakeSangaboard]:
    _app()
    sb = FakeSangaboard()
    return MotionController(sb, ObjMgr(backlash_x, backlash_y, backlash_z), FakeConfig()), sb


def test_plan_axis_zero_delta_passes_through() -> None:
    assert MotionController._plan_axis(0, 25.0, 100, True) == (0, 25.0)
    assert MotionController._plan_axis(0, -50.0, 100, False) == (0, -50.0)


def test_plan_axis_zero_backlash_passes_through() -> None:
    assert MotionController._plan_axis(500, 0.0, 0, True) == (500, 0.0)
    assert MotionController._plan_axis(-500, 0.0, 0, True) == (-500, 0.0)


def test_plan_axis_fresh_state_adds_half_backlash_pre_move() -> None:
    motor, new_slack = MotionController._plan_axis(1000, 0.0, 100, True)
    assert motor == 1050   # +1000 load + 50 slack take-up
    assert new_slack == 50.0


def test_plan_axis_full_reversal_traverses_full_band() -> None:
    motor, new_slack = MotionController._plan_axis(1000, -50.0, 100, True)
    assert motor == 1100   # +1000 load + 100 full-band traverse
    assert new_slack == 50.0


def test_plan_axis_same_direction_continuation_no_pre_move() -> None:
    motor, new_slack = MotionController._plan_axis(200, 50.0, 100, True)
    assert motor == 200
    assert new_slack == 50.0


def test_plan_axis_apply_backlash_false_passes_raw_and_updates_slack() -> None:
    """Joystick / calibration path: no pre-move, but slack tracks the raw
    motor delta so the next compensated move sees the right band side."""
    motor, new_slack = MotionController._plan_axis(30, 0.0, 100, False)
    assert motor == 30
    assert new_slack == 30.0
    # Continued raw motion clamps slack at +half.
    motor2, new_slack2 = MotionController._plan_axis(40, new_slack, 100, False)
    assert motor2 == 40
    assert new_slack2 == 50.0   # clamped to +backlash/2
    # Reversing raw delta brings slack back through the band.
    motor3, new_slack3 = MotionController._plan_axis(-30, new_slack2, 100, False)
    assert motor3 == -30
    assert new_slack3 == 20.0


def test_preview_move_rel_reports_backlash_without_mutating_slack() -> None:
    ctrl, sb = _ctrl(backlash_x=100, backlash_y=80)

    preview = ctrl.preview_move_rel(1000, 200, 0)

    assert preview["motor_dx"] == 1050
    assert preview["motor_dy"] == 240
    assert preview["extra_x"] == 50
    assert preview["extra_y"] == 40
    assert preview["slack_before"] == (0.0, 0.0, 0.0)
    assert preview["slack_after"] == (50.0, 40.0, 0.0)
    assert ctrl._slack_x == 0.0
    assert ctrl._slack_y == 0.0
    assert sb.moves == []

    assert ctrl.move_rel(1000, 200, 0) is True
    assert sb.moves == [(1050, 240, 0)]


# Integrated MotionController tests, verify the motor commands and slack state across realistic sequences.

def test_first_move_after_init_takes_up_half_backlash() -> None:
    ctrl, sb = _ctrl(backlash_x=100)
    ok = ctrl.move_rel(1000, 0, 0)
    assert ok is True
    assert sb.moves == [(1050, 0, 0)]
    assert ctrl._slack_x == pytest.approx(50.0)


def test_full_reversal_inserts_full_band_compensation() -> None:
    ctrl, sb = _ctrl(backlash_x=100)
    ctrl.move_rel(1000, 0, 0)    # commits load to +side, slack=+50
    ctrl.move_rel(-500, 0, 0)    # full reversal: motor = -500 - 100 = -600
    assert sb.moves[-1] == (-600, 0, 0)
    assert ctrl._slack_x == pytest.approx(-50.0)


def test_continuation_in_same_direction_has_no_pre_move() -> None:
    ctrl, sb = _ctrl(backlash_x=100)
    ctrl.move_rel(1000, 0, 0)   # slack -> +50
    sb.moves.clear()
    ctrl.move_rel(200, 0, 0)    # same direction, slack already at +50
    assert sb.moves == [(200, 0, 0)]
    assert ctrl._slack_x == pytest.approx(50.0)


def test_axes_track_slack_independently() -> None:
    ctrl, sb = _ctrl(backlash_x=100, backlash_y=80, backlash_z=60)
    ctrl.move_rel(500, 0, 0)        # X slack -> +50, Y/Z untouched (still 0)
    ctrl.move_rel(0, 300, 0)        # Y slack -> +40, X unchanged
    ctrl.move_rel(0, 0, -100)       # Z slack -> -30
    assert ctrl._slack_x == pytest.approx(50.0)
    assert ctrl._slack_y == pytest.approx(40.0)
    assert ctrl._slack_z == pytest.approx(-30.0)
    # Reversing only Y must not insert a pre-move on X or Z.
    sb.moves.clear()
    ctrl.move_rel(0, -100, 0)
    assert sb.moves == [(0, -180, 0)]   # -100 load + 80 full-band Y
    assert ctrl._slack_y == pytest.approx(-40.0)
    assert ctrl._slack_x == pytest.approx(50.0)
    assert ctrl._slack_z == pytest.approx(-30.0)


def test_invalidate_backlash_history_clears_all_axes() -> None:
    ctrl, sb = _ctrl(backlash_x=100, backlash_y=80, backlash_z=60)
    ctrl.move_rel(500, 300, -100)
    assert ctrl._slack_x != 0 or ctrl._slack_y != 0 or ctrl._slack_z != 0
    ctrl.invalidate_backlash_history()
    assert ctrl._slack_x == 0.0
    assert ctrl._slack_y == 0.0
    assert ctrl._slack_z == 0.0


def test_deenergize_motors_invalidates_slack() -> None:
    ctrl, _sb = _ctrl(backlash_x=100)
    ctrl.move_rel(1000, 0, 0)
    assert ctrl._slack_x == pytest.approx(50.0)
    ctrl.deenergize_motors()
    assert ctrl._slack_x == 0.0
    assert ctrl._slack_y == 0.0
    assert ctrl._slack_z == 0.0


def test_calibration_move_does_not_pre_move_but_updates_slack() -> None:
    ctrl, sb = _ctrl(backlash_x=100)
    ctrl.calibration_move_rel(30, 0, 0)
    assert sb.moves == [(30, 0, 0)]
    assert ctrl._slack_x == pytest.approx(30.0)
    # Next compensated move starts from this slack state.
    sb.moves.clear()
    ctrl.move_rel(200, 0, 0)
    # slack +30 -> after +200, pre = +50 - 30 = +20; motor = 220.
    assert sb.moves == [(220, 0, 0)]
    assert ctrl._slack_x == pytest.approx(50.0)


def test_zero_backlash_profile_emits_no_pre_move() -> None:
    """A profile with backlash=0 (factory defaults) must behave exactly as a passthrough."""
    ctrl, sb = _ctrl(backlash_x=0, backlash_y=0, backlash_z=0)
    ctrl.move_rel(100, -50, 30)
    ctrl.move_rel(-200, 100, -10)
    assert sb.moves == [(100, -50, 30), (-200, 100, -10)]
    assert ctrl._slack_x == 0.0
    assert ctrl._slack_y == 0.0
    assert ctrl._slack_z == 0.0
