"""Test the objective detection logic."""

from retroscope.domain.objective_detection import DetectorState, Event, Phase, step

KW = dict(
    dark_threshold_pct=15.0,
    dark_duration_ms=200,
    recovery_threshold_pct=40.0,
)


def _seed(state: DetectorState, brightness: float, n: int, t0: float = 0.0) -> float:
    t = t0
    for _ in range(n):
        step(state, brightness, now_ms=t, **KW)
        t += 100.0
    return t


def test_no_event_before_history_seeded():
    s = DetectorState()
    # Only 4 samples (min is 5). No transitions even on a black frame.
    for i in range(4):
        assert step(s, 100.0, now_ms=i * 100.0, **KW) is Event.NONE


def test_complete_switch_cycle_emits():
    s = DetectorState()
    t = _seed(s, 100.0, 10)
    # Drop into darkness
    assert step(s, 5.0, now_ms=t, **KW) is Event.NONE
    assert s.phase is Phase.DARK
    t += 250.0   # past dark_duration_ms (200)
    # Recovery above 40 % of average
    assert step(s, 60.0, now_ms=t, **KW) is Event.SWITCH
    assert s.phase is Phase.NORMAL


def test_too_brief_dark_is_spurious():
    s = DetectorState()
    t = _seed(s, 100.0, 10)
    step(s, 5.0, now_ms=t, **KW)            # enter DARK
    t += 50.0                               # well under 200 ms
    ev = step(s, 60.0, now_ms=t, **KW)      # premature recovery
    assert ev is Event.NONE
    assert s.phase is Phase.NORMAL


def test_long_dark_aborts_silently():
    s = DetectorState()
    t = _seed(s, 100.0, 10)
    step(s, 5.0, now_ms=t, **KW)            # enter DARK
    t += 4000.0                             # > max_dark_ms (3000)
    ev = step(s, 60.0, now_ms=t, **KW)
    assert ev is Event.NONE
    assert s.phase is Phase.NORMAL


def test_all_black_scene_ignored():
    s = DetectorState()
    # avg < 1.0 -> never triggers
    for i in range(20):
        assert step(s, 0.5, now_ms=i * 100.0, **KW) is Event.NONE
