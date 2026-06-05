"""Tests for the reworked autofocus routine.

Note: Partially AI-generated
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("cv2")

from PySide6.QtCore import QCoreApplication

from retroscope.domain.focus_metrics import parabolic_peak
import retroscope.services.autofocus as autofocus
from retroscope.services.autofocus import (
    AutofocusService,
    _AutofocusWorker,
    autofocus_sample_positions,
)


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class FakeConfig:
    def __init__(self, values: dict | None = None) -> None:
        self.values: dict = values or {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value


class FakeMotionController:
    """Records every Z move in order so tests can replay the trajectory."""

    def __init__(self) -> None:
        self.moves: list[int] = []
        self.blocking_moves: list[int] = []
        self.position = 0

    def move_z(self, delta: int) -> None:
        self.moves.append(int(delta))
        self.position += int(delta)
        return True

    def move_z_blocking(self, delta: int) -> bool:
        self.blocking_moves.append(int(delta))
        return self.move_z(delta)


class PeakCamera:
    """Live raw focus stream whose score depends on the current z position."""

    def __init__(self, position_fn, peak_z: int = 0, sigma: float = 80.0) -> None:
        self._pos_fn = position_fn
        self._peak_z = peak_z
        self._sigma = sigma
        self.scores_returned = 0
        self.frame_calls = 0
        self.sample_positions: list[int] = []

    def _variance_for_z(self, z: int) -> float:
        dz = z - self._peak_z
        return 50.0 + 5000.0 * np.exp(-(dz * dz) / (2.0 * self._sigma * self._sigma))

    def raw_focus_sequence(self) -> int:
        return self.scores_returned

    def raw_focus_status(self):
        return self.scores_returned, self._variance_for_z(self._pos_fn()), 0.0, "test"

    def wait_for_next_raw_focus_score(self, after_sequence: int | None = None, timeout: float = 0.5):
        del after_sequence, timeout
        self.scores_returned += 1
        self.sample_positions.append(int(self._pos_fn()))
        return self._variance_for_z(self._pos_fn())

    def get_latest_frame(self):
        self.frame_calls += 1
        raise AssertionError("autofocus must not sample camera frames")


class FlatCamera:
    """Raw focus stream that always returns a blank-field score."""

    def __init__(self) -> None:
        self.scores_returned = 0

    def raw_focus_sequence(self) -> int:
        return self.scores_returned

    def wait_for_next_raw_focus_score(self, after_sequence: int | None = None, timeout: float = 0.5):
        del after_sequence, timeout
        self.scores_returned += 1
        return 0.0

    def get_latest_frame(self):
        raise AssertionError("autofocus must not sample camera frames")


class LatestOnlyCamera:
    def __init__(self, latest: float | None, age: float | None) -> None:
        self.latest = latest
        self.age = age
        self.waits: list[tuple[int | None, float]] = []

    def raw_focus_sequence(self) -> int:
        return 1

    def raw_focus_status(self):
        return 1, self.latest, self.age, "test"

    def wait_for_next_raw_focus_score(self, after_sequence: int | None = None, timeout: float = 0.5):
        self.waits.append((after_sequence, timeout))
        return None


def _fast_config() -> FakeConfig:
    return FakeConfig({
        "autofocus.settle_ms": 50,
        "autofocus.move_start_ms": 100,
        "autofocus.coarse_positions": 11,
        "autofocus.fine_positions": 13,
        "autofocus.samples_per_position": 1,
        "autofocus.min_confidence": 50.0,
    })


def _profile(focus_stack_step: int = 10, dof_steps: int = 100, autofocus_range_steps: int = 200) -> SimpleNamespace:
    return SimpleNamespace(
        focus_stack_step=focus_stack_step,
        dof_steps=dof_steps,
        autofocus_range_steps=autofocus_range_steps,
    )


class _ObjMgr:
    def __init__(self, profile) -> None:
        self._p = profile

    def current_profile(self):
        return self._p

def test_parabolic_peak_interpolates_between_samples() -> None:
    # Symmetric parabola -> peak at z_mid.
    assert parabolic_peak(-10, 100.0, 0, 400.0, 10, 100.0) == 0
    # Skewed left -> peak < 0.
    assert parabolic_peak(-10, 300.0, 0, 400.0, 10, 100.0) < 0
    # Skewed right -> peak > 0.
    assert parabolic_peak(-10, 100.0, 0, 400.0, 10, 300.0) > 0


def test_parabolic_peak_falls_back_to_mid_when_not_concave_down() -> None:
    # Monotonic increase -> no concave-down peak -> return mid.
    assert parabolic_peak(0, 10.0, 5, 20.0, 10, 30.0) == 5
    # Convex-up trough -> return mid (no max in the triple).
    assert parabolic_peak(-10, 300.0, 0, 100.0, 10, 300.0) == 0


def test_parabolic_peak_clamps_to_neighbouring_samples() -> None:
    # Even a heavily skewed but still concave-down triple cannot send the
    # interpolated peak past z_left or z_right.
    peak = parabolic_peak(-10, 399.0, 0, 400.0, 10, 1.0)
    assert -10 <= peak <= 10


# Worker accuracy
def test_autofocus_lands_near_true_peak() -> None:
    _app()
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, dof_steps=100, autofocus_range_steps=300)
    camera = PeakCamera(lambda: motion.position, peak_z=60, sigma=50.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), _fast_config())
    worker.run()

    # fine_step = max(focus_stack_step*2, 5) = 20
    assert abs(motion.position - 60) <= 20, motion.position


def test_autofocus_fine_sweep_is_symmetric_around_coarse_peak() -> None:
    """The recorded z positions during the fine sweep must lie symmetrically around the best coarse position."""
    _app()
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, dof_steps=100, autofocus_range_steps=300)
    camera = PeakCamera(lambda: motion.position, peak_z=80, sigma=40.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), _fast_config())

    path: list[int] = []
    motion_move = motion.move_z

    def spy_move_z(delta: int) -> None:
        motion_move(delta)
        path.append(motion.position)

    motion.move_z = spy_move_z
    worker.run()

    above = sum(1 for z in path if z > 80)
    below = sum(1 for z in path if z < 80)
    assert above > 0 and below > 0, f"fine sweep not symmetric: {path}"


def test_autofocus_coarse_sweep_samples_center_up_return_down(monkeypatch) -> None:
    """Coarse samples centre once, then upward half, then downward half."""
    _app()
    monkeypatch.setattr(autofocus.time, "sleep", lambda _seconds: None)
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, autofocus_range_steps=100)
    cfg = _fast_config()
    cfg.set("autofocus.coarse_positions", 7)
    cfg.set("autofocus.fine_positions", 5)
    camera = PeakCamera(lambda: motion.position, peak_z=0, sigma=30.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), cfg)

    worker.run()

    assert camera.sample_positions[:7] == [0, 33, 66, 99, -33, -66, -99]
    assert motion.moves[:7] == [33, 33, 33, -99, -33, -33, -33]
    assert motion.blocking_moves[:7] == [33, 33, 33, -99, -33, -33, -33]


def test_autofocus_fine_sweep_starts_at_best_coarse_base(monkeypatch) -> None:
    """Fine sweep first moves to the best coarse Z and scans around that base."""
    _app()
    monkeypatch.setattr(autofocus.time, "sleep", lambda _seconds: None)
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, autofocus_range_steps=100)
    cfg = _fast_config()
    cfg.set("autofocus.coarse_positions", 7)
    cfg.set("autofocus.fine_positions", 5)
    camera = PeakCamera(lambda: motion.position, peak_z=50, sigma=20.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), cfg)

    worker.run()

    assert camera.sample_positions[:7] == [0, 33, 66, 99, -33, -66, -99]
    assert camera.sample_positions[7:12] == [66, 86, 106, 46, 26]


def test_autofocus_sweep_waits_after_moves_before_sampling(monkeypatch) -> None:
    """Adjacent sweep moves use settle delay, return-to-centre uses move-start delay."""
    _app()
    sleeps: list[float] = []
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, autofocus_range_steps=100)
    cfg = _fast_config()
    cfg.set("autofocus.coarse_positions", 7)
    cfg.set("autofocus.fine_positions", 5)
    camera = PeakCamera(lambda: motion.position, peak_z=0, sigma=30.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), cfg)
    monkeypatch.setattr(
        worker,
        "_sleep_cancelable",
        lambda seconds: sleeps.append(round(float(seconds), 3)) or True,
    )

    worker.run()

    assert sleeps[:5] == [0.05, 0.05, 0.05, 0.1, 0.05]


def test_autofocus_focus_timeout_scales_with_analysis_fps() -> None:
    _app()
    cfg = _fast_config()
    cfg.set("camera.fps", 2)
    worker = _AutofocusWorker(LatestOnlyCamera(None, None), None, None, cfg)

    worker._load_config()

    assert worker._focus_score_timeout_s() == pytest.approx(1.25)


def test_autofocus_uses_recent_latest_score_from_settle_window() -> None:
    _app()
    camera = LatestOnlyCamera(4321.0, 0.05)
    worker = _AutofocusWorker(camera, None, None, _fast_config())
    worker._settle_s = 0.20
    worker._samples_per_position = 1

    assert worker._grab_score() == pytest.approx(4321.0)
    assert len(camera.waits) == 1


def test_autofocus_min_confidence_aborts_and_returns_to_start() -> None:
    _app()
    motion = FakeMotionController()
    motion.position = 0
    profile = _profile()
    cfg = _fast_config()
    cfg.set("autofocus.min_confidence", 1000.0)   # impossibly high
    worker = _AutofocusWorker(FlatCamera(), motion, _ObjMgr(profile), cfg)

    failed_reasons: list[str] = []
    worker.failed.connect(failed_reasons.append)
    finished_flag = []
    worker.finished.connect(lambda: finished_flag.append(True))

    worker.run()

    assert failed_reasons, "min-confidence guard should have fired"
    assert "below threshold" in failed_reasons[0]
    assert finished_flag == [True]
    # After the failure path returns Z to 0 (start position).
    assert motion.position == 0, motion.moves


def test_autofocus_cancel_finishes_without_returning_to_start(monkeypatch) -> None:
    _app()
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, autofocus_range_steps=100)
    cfg = _fast_config()
    cfg.set("autofocus.coarse_positions", 7)
    cfg.set("autofocus.fine_positions", 5)
    camera = PeakCamera(lambda: motion.position, peak_z=0, sigma=30.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), cfg)
    failed_reasons: list[str] = []
    worker.failed.connect(failed_reasons.append)

    def cancel_after_first_wait(_seconds: float) -> bool:
        worker.request_cancel()
        return False

    monkeypatch.setattr(worker, "_sleep_cancelable", cancel_after_first_wait)

    worker.run()

    assert failed_reasons == ["Cancelled"]
    assert motion.moves == [33]
    assert motion.position == 33


def test_autofocus_service_exposes_cancelling_until_finished() -> None:
    _app()
    service = AutofocusService(None, None, None, None)
    service._busy = True

    class FakeWorker:
        def __init__(self) -> None:
            self.cancel_requested = False

        def request_cancel(self) -> None:
            self.cancel_requested = True

    worker = FakeWorker()
    service._worker = worker
    seen: list[bool] = []
    service.cancelling_changed.connect(seen.append)

    service.cancel()

    assert worker.cancel_requested is True
    assert service.cancelling is True
    assert seen == [True]

    service._on_finished()

    assert service.cancelling is False
    assert seen == [True, False]


def test_autofocus_progress_reaches_1_0_only_after_final_commit(monkeypatch) -> None:
    _app()
    motion = FakeMotionController()
    profile = _profile(focus_stack_step=10, dof_steps=100, autofocus_range_steps=300)
    camera = PeakCamera(lambda: motion.position, peak_z=20, sigma=40.0)
    worker = _AutofocusWorker(camera, motion, _ObjMgr(profile), _fast_config())

    events: list[tuple[str, float]] = []
    worker.progress.connect(lambda v: events.append(("progress", float(v))))
    worker.finished.connect(lambda: events.append(("finished", 0.0)))
    monkeypatch.setattr(
        worker,
        "_sleep_cancelable",
        lambda seconds: events.append(("sleep", float(seconds))) or True,
    )

    motion_move = motion.move_z

    def spy_move_z(delta: int) -> None:
        events.append(("move", float(len(motion.moves))))
        return motion_move(delta)

    motion.move_z = spy_move_z
    worker.run()

    progress_events = [v for kind, v in events if kind == "progress"]
    assert progress_events[-1] == 1.0
    assert events[-1][0] == "finished"
    # The last move and its wait must both happen before the final progress emit.
    last_move_index = max(i for i, (k, _) in enumerate(events) if k == "move")
    last_sleep_index = max(i for i, (k, _) in enumerate(events) if k == "sleep")
    last_progress_index = max(i for i, (k, _) in enumerate(events) if k == "progress")
    assert last_move_index < last_sleep_index < last_progress_index, events


# Sample-position plan
def test_autofocus_sample_positions_honors_coarse_positions_arg() -> None:
    profile = _profile(autofocus_range_steps=1000, dof_steps=100, focus_stack_step=10)
    positions = autofocus_sample_positions(profile, coarse_positions=9)
    assert len(positions) == 9
    assert positions[0] == 0
    # Even-valued count gets bumped to odd.
    positions_even = autofocus_sample_positions(profile, coarse_positions=10)
    assert len(positions_even) == 11


# Settings bridge preset
def test_settings_bridge_autofocus_speed_preset_balanced_sets_defaults(tmp_path, monkeypatch) -> None:
    """Selecting a named preset on the bridge updates all four numeric defaults."""
    _app()
    import retroscope.services.config_store as config_store

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    from retroscope.services.config_store import ConfigStore
    from retroscope.services.image_store import ImageStore
    from retroscope.bridge.settings_bridge import SettingsBridge

    cfg = ConfigStore(autosave_delay_ms=0)
    cfg.load()
    image_store = ImageStore(cfg)
    bridge = SettingsBridge(cfg, image_store)

    bridge.setAutofocusSpeedPreset("fast")
    assert bridge.autofocusSettleMs == 1000
    assert bridge.autofocusMoveStartMs == 400
    assert bridge.autofocusCoarsePositions == 11
    assert bridge.autofocusFinePositions == 13
    assert bridge.autofocusSamplesPerPosition == 1

    bridge.setAutofocusSpeedPreset("slow")
    assert bridge.autofocusSettleMs == 1000
    assert bridge.autofocusFinePositions == 31

    # "custom" leaves the slider values intact.
    bridge.setAutofocusSettleMs(1000)
    bridge.setAutofocusSpeedPreset("custom")
    assert bridge.autofocusSettleMs == 1000


def test_settings_bridge_autofocus_coarse_positions_force_odd(tmp_path, monkeypatch) -> None:
    """Coarse positions must always be odd for the symmetric centre-out sweep."""
    _app()
    import retroscope.services.config_store as config_store

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    from retroscope.services.config_store import ConfigStore
    from retroscope.services.image_store import ImageStore
    from retroscope.bridge.settings_bridge import SettingsBridge

    cfg = ConfigStore(autosave_delay_ms=0)
    cfg.load()
    bridge = SettingsBridge(cfg, ImageStore(cfg))
    bridge.setAutofocusCoarsePositions(14)
    assert bridge.autofocusCoarsePositions == 15

    bridge.setAutofocusCoarsePositions(40)
    assert bridge.autofocusCoarsePositions == 41


def test_settings_bridge_autofocus_fine_positions_force_odd(tmp_path, monkeypatch) -> None:
    _app()
    import retroscope.services.config_store as config_store

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    from retroscope.services.config_store import ConfigStore
    from retroscope.services.image_store import ImageStore
    from retroscope.bridge.settings_bridge import SettingsBridge

    cfg = ConfigStore(autosave_delay_ms=0)
    cfg.load()
    bridge = SettingsBridge(cfg, ImageStore(cfg))
    bridge.setAutofocusFinePositions(12)
    assert bridge.autofocusFinePositions == 13

    bridge.setAutofocusFinePositions(40)
    assert bridge.autofocusFinePositions == 41
