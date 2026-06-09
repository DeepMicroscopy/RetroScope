"""Evaluation harness: backlash-compensation move planning."""

from __future__ import annotations

import pytest

from retroscope.evaluation.compensation import (
    CompensatedMover,
    ExcursionGuard,
    plan_hysteresis,
    plan_none,
    plan_sign,
)


def test_plan_none_passthrough():
    assert plan_none(1000) == 1000
    assert plan_none(-7) == -7


def test_plan_sign_adds_full_backlash_on_reversal():
    # fresh -> no compensation, sets direction
    motor, d = plan_sign(1000, 0, 100)
    assert (motor, d) == (1000, 1)
    # same direction -> no compensation
    motor, d = plan_sign(200, d, 100)
    assert (motor, d) == (200, 1)
    # reversal -> add full backlash in the new direction
    motor, d = plan_sign(-500, d, 100)
    assert (motor, d) == (-600, -1)


def test_plan_hysteresis_matches_motion_controller():
    """plan_hysteresis must equal MotionController._plan_axis(apply_backlash=True)."""
    pytest.importorskip("PySide6")
    from retroscope.services.motion_controller import MotionController

    cases = [(1000, 0.0, 100), (-500, 50.0, 100), (200, 50.0, 100),
             (0, 13.0, 100), (300, -40.0, 80), (-300, 40.0, 0)]
    for delta, slack, backlash in cases:
        assert plan_hysteresis(delta, slack, backlash) == \
            MotionController._plan_axis(delta, slack, backlash, True)


def test_plan_hysteresis_band_example():
    # b=100: first +1000 -> +1050 (slack +50); then -500 -> -600 (slack -50)
    motor, slack = plan_hysteresis(1000, 0.0, 100)
    assert (motor, slack) == (1050, 50.0)
    motor, slack = plan_hysteresis(-500, slack, 100)
    assert (motor, slack) == (-600, -50.0)


class _FakeSangaboard:
    def __init__(self):
        self.moves = []

    def move_rel_blocking(self, dx, dy, dz, timeout=None):
        self.moves.append((dx, dy, dz))
        return True


def test_mover_sends_compensated_single_axis_moves():
    sb = _FakeSangaboard()
    mover = CompensatedMover(sb, (100, 200, 20))
    assert mover.move_axis(0, 1000, "hysteresis") == 1050
    assert sb.moves[-1] == (1050, 0, 0)
    assert mover.move_axis(1, 1000, "none") == 1000
    assert sb.moves[-1] == (0, 1000, 0)


def test_mover_return_to_start_undoes_actual_motor_net():
    sb = _FakeSangaboard()
    mover = CompensatedMover(sb, (100, 0, 0))
    mover.move_axis(0, 1000, "hysteresis")
    mover.return_to_start()
    assert sb.moves == [(1050, 0, 0), (-1050, 0, 0)]


def test_mover_excursion_guard():
    sb = _FakeSangaboard()
    mover = CompensatedMover(sb, (0, 0, 0), max_excursion=500)
    mover.move_axis(0, 400, "none")
    with pytest.raises(ExcursionGuard):
        mover.move_axis(0, 200, "none")


def test_mover_excursion_guard_checks_compensated_motor_net():
    sb = _FakeSangaboard()
    mover = CompensatedMover(sb, (100, 0, 0), max_excursion=1000)
    with pytest.raises(ExcursionGuard):
        mover.move_axis(0, 960, "hysteresis")
    assert sb.moves == []
