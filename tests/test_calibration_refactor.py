"""Test the calibration-related services and bridge logic."""

from __future__ import annotations

import time
import threading
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage

from retroscope.domain.focus_metrics import grayscale_focus_score
from retroscope.bridge.direct_camera_bridge import DirectCameraBridge
from retroscope.services.autofocus import _AutofocusWorker, autofocus_sample_positions
from retroscope.services.backlash_measurement import center_crop, measure_offset
from retroscope.bridge.calibration_bridge import CalibrationBridge
from retroscope.services.camera_service import CameraService
from retroscope.services.config_store import ConfigStore
from retroscope.services.motion_controller import MotionController
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


class FakeSangaboard:
    def __init__(self) -> None:
        self.moves: list[tuple[int, int, int]] = []
        self.stopped = False

    def move_rel(self, dx: int, dy: int, dz: int, coalesce: bool = False) -> None:
        self.moves.append((dx, dy, dz))

    def stop_motors(self) -> None:
        self.stopped = True


class _FakePixelFormat:
    name = "Format_NV12"


class _FakeSurfaceFormat:
    def pixelFormat(self):
        return _FakePixelFormat()


class _FakeMappedVideoFrame:
    def __init__(self, y: np.ndarray, uv: np.ndarray, image: QImage) -> None:
        self._y = np.ascontiguousarray(y, dtype=np.uint8)
        self._uv = np.ascontiguousarray(uv, dtype=np.uint8)
        self._image = image
        self.map_calls = 0

    def surfaceFormat(self):
        return _FakeSurfaceFormat()

    def width(self) -> int:
        return int(self._y.shape[1])

    def height(self) -> int:
        return int(self._y.shape[0])

    def map(self, _mode) -> bool:
        self.map_calls += 1
        return True

    def unmap(self) -> None:
        pass

    def bytesPerLine(self, plane: int) -> int:
        return int(self._y.shape[1] if plane == 0 else self._uv.shape[1])

    def mappedBytes(self, plane: int) -> int:
        return int(self._y.nbytes if plane == 0 else self._uv.nbytes)

    def bits(self, plane: int = 0):
        return memoryview(self._y if plane == 0 else self._uv)

    def toImage(self) -> QImage:
        return self._image


def test_config_store_autosaves_immediately_when_delay_is_zero(tmp_path, monkeypatch) -> None:
    _app()
    import retroscope.services.config_store as config_store

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    store = ConfigStore(autosave_delay_ms=0)
    store.load()

    store.set("ui.active_objective", "20x")

    assert (tmp_path / "config.json").exists()
    assert '"active_objective": "20x"' in (tmp_path / "config.json").read_text(encoding="utf-8")


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


def test_autofocus_plan_samples_center_then_positive_then_negative() -> None:
    profile = SimpleNamespace(autofocus_range_steps=1000, dof_steps=100, focus_stack_step=10)

    positions = autofocus_sample_positions(profile)

    assert positions[0] == 0
    assert positions[1] > 0
    assert max(positions) > 0
    assert min(positions) < 0
    assert positions.index(min(positions)) > positions.index(max(positions))


def test_histogram_keeps_neighboring_peak_stable_during_one_bin_jitter() -> None:
    _app()
    service = CameraService(FakeConfig())
    try:
        frame_a = np.full((80, 120, 3), 100, dtype=np.uint8)
        frame_b = np.full((80, 120, 3), 104, dtype=np.uint8)

        service._smooth_histogram(service._compute_histogram(frame_a))
        hist = service._smooth_histogram(service._compute_histogram(frame_b))

        assert hist[25] > 80
        assert hist[26] > 45
    finally:
        service.shutdown()


def test_histogram_uses_frame_area_independent_scaling() -> None:
    _app()
    small = CameraService(FakeConfig())
    large = CameraService(FakeConfig())
    try:
        small_frame = np.full((40, 60, 3), 120, dtype=np.uint8)
        large_frame = np.full((160, 240, 3), 120, dtype=np.uint8)

        small_hist = small._smooth_histogram(small._compute_histogram(small_frame))
        large_hist = large._smooth_histogram(large._compute_histogram(large_frame))

        assert large_hist == small_hist
        assert max(large_hist) == 100
    finally:
        small.shutdown()
        large.shutdown()


def test_grayscale_focus_score_drops_under_blur() -> None:
    pytest.importorskip("cv2")
    import cv2

    sharp = (np.indices((180, 240)).sum(axis=0) % 2 * 255).astype(np.uint8)
    blurred = cv2.GaussianBlur(sharp, (0, 0), 3.0)

    assert grayscale_focus_score(sharp) > grayscale_focus_score(blurred) * 5


def test_camera_service_frame_delivery_emits_brightness_without_duplicate_focus() -> None:
    _app()
    service = CameraService(FakeConfig())
    try:
        raw_scores: list[float] = []
        brightness_values: list[float] = []
        service.focus_score_updated.connect(raw_scores.append)
        service.brightness_updated.connect(brightness_values.append)
        frame = np.full((24, 32, 3), 128, dtype=np.uint8)

        service.on_frame_ready(frame)

        assert service.get_latest_frame() is frame
        assert raw_scores == []
        assert brightness_values == pytest.approx([128.0])
    finally:
        service.shutdown()


def test_camera_service_frame_analysis_toggle_skips_focus_and_brightness() -> None:
    _app()
    service = CameraService(FakeConfig())
    try:
        focus_scores: list[float] = []
        brightness_values: list[float] = []
        service.focus_score_updated.connect(focus_scores.append)
        service.brightness_updated.connect(brightness_values.append)
        frame = np.full((24, 32, 3), 128, dtype=np.uint8)

        service.set_frame_analysis_enabled(False)
        service.on_frame_ready(frame)

        assert service.get_latest_frame() is frame
        assert focus_scores == []
        assert brightness_values == []
    finally:
        service.shutdown()


def test_direct_camera_bridge_performance_toggles_gate_analysis_and_preview(monkeypatch) -> None:
    _app()

    class FakeCameraService:
        def __init__(self) -> None:
            self.frames: list[np.ndarray] = []
            self.focus_scores: list[float] = []
            self.frame_ready = threading.Event()

        def on_frame_ready(self, frame: np.ndarray) -> None:
            self.frames.append(frame)
            self.frame_ready.set()

        def on_focus_score_ready(self, score: float) -> None:
            self.focus_scores.append(score)

    class FakeVideoSink:
        def __init__(self) -> None:
            self.frames: list[object] = []

        def setVideoFrame(self, frame: object) -> None:
            self.frames.append(frame)

    service = FakeCameraService()
    sink = FakeVideoSink()
    bridge = DirectCameraBridge(service, enabled=True)
    bridge._output_sink = sink
    bridge._tap_interval_s = 0.0
    frame = object()
    analysis_frame = np.ones((4, 4, 3), dtype=np.uint8)
    conversions: list[object] = []

    def convert_frame(received_frame: object):
        conversions.append(received_frame)
        return analysis_frame, 55.0

    monkeypatch.setattr(bridge, "_frame_to_rgb_array_and_focus", convert_frame)

    bridge.setFrameAnalysisEnabled(False)
    bridge._on_video_frame(frame)
    time.sleep(0.02)

    assert conversions == []
    assert service.focus_scores == []
    assert service.frames == []
    assert sink.frames == [frame]

    sink.frames.clear()
    bridge.setFrameAnalysisEnabled(True)
    bridge.setLiveVideoEnabled(False)
    sink.frames.clear()

    bridge._on_video_frame(frame)

    assert service.frame_ready.wait(timeout=1.0)
    assert conversions == [frame]
    assert service.focus_scores == [55.0]
    assert len(service.frames) == 1
    assert service.frames[0] is analysis_frame
    assert sink.frames == []
    bridge.stop()


def test_source_focus_score_can_be_waited_for_independently_of_frame() -> None:
    _app()
    service = CameraService(FakeConfig())
    raw_scores: list[float] = []
    sources: list[str] = []
    service.focus_score_updated.connect(raw_scores.append)
    service.focus_source_updated.connect(sources.append)
    seq = service.focus_sequence()

    service.on_focus_score_ready(1234.5)

    assert service.wait_for_next_focus_score(after_sequence=seq, timeout=0.0) == pytest.approx(1234.5)
    assert raw_scores == pytest.approx([1234.5])
    assert sources == ["source"]


def test_raw_focus_score_bypasses_source_stabilizer_for_autofocus() -> None:
    _app()
    service = CameraService(FakeConfig())
    seq = service.raw_focus_sequence()

    service.on_focus_score_ready(30.0)
    service.on_focus_score_ready(4400.0)

    assert service.wait_for_next_raw_focus_score(after_sequence=seq, timeout=0.0) == pytest.approx(4400.0)
    assert service._latest_source_focus_score == pytest.approx(30.0)


def test_source_focus_score_becomes_unavailable_when_stale() -> None:
    _app()
    service = CameraService(FakeConfig())

    service.on_focus_score_ready(1234.5)
    assert service.source_focus_available() is True

    service._latest_source_focus_t = time.monotonic() - 2.0

    assert service.source_focus_available() is False


def test_source_focus_rejects_isolated_upward_spikes() -> None:
    """Verify the spike rejector (protects the displayed score from one-frame flicker)."""
    _app()
    service = CameraService(FakeConfig())

    expected = [30.0, 30.0, 32.0, 32.0, 4100.0]
    inputs = [30.0, 4400.0, 32.0, 4200.0, 4100.0]
    observed: list[float] = []
    for value in inputs:
        service.on_focus_score_ready(value)
        observed.append(service._latest_source_focus_score or 0.0)

    assert observed == pytest.approx(expected)


class FakeRawFocusCamera:
    def __init__(self, scores: list[float] | None = None) -> None:
        self.scores = list(scores or [])
        self.seq = 0
        self.frame_calls = 0
        self.raw_waits: list[tuple[int | None, float]] = []

    def raw_focus_sequence(self) -> int:
        return self.seq

    def raw_focus_status(self):
        latest = self.scores[0] if self.scores else None
        return self.seq, latest, 0.0, "test"

    def wait_for_next_raw_focus_score(self, after_sequence: int | None = None, timeout: float = 0.5):
        self.raw_waits.append((after_sequence, timeout))
        if not self.scores:
            return None
        self.seq += 1
        return self.scores.pop(0)

    def wait_for_next_frame(self, timeout: float = 0.5):
        del timeout
        self.frame_calls += 1
        raise AssertionError("autofocus must not use camera frames")


def test_autofocus_score_uses_raw_live_focus_scores_not_frames() -> None:
    _app()
    camera = FakeRawFocusCamera([100.0, 300.0])
    worker = _AutofocusWorker(camera, None, None, None)
    worker._samples_per_position = 2

    score = worker._grab_score()

    assert score == pytest.approx(200.0)
    assert camera.frame_calls == 0
    assert len(camera.raw_waits) == 2


def test_autofocus_score_fails_without_fresh_raw_focus_score() -> None:
    _app()
    worker = _AutofocusWorker(FakeRawFocusCamera([]), None, None, None)

    assert worker._grab_score() is None


def test_joystick_release_clears_pending_accumulator() -> None:
    _app()
    sb = FakeSangaboard()
    ctrl = MotionController(sb, FakeObjectiveManager(), FakeConfig())
    ctrl._set_joystick_center(0.0, 0.0)
    ctrl._joystick_x_active = True
    ctrl._joystick_x_sign = 1
    ctrl._dx_accum = 3.4

    ctrl.on_axes_updated(0, 0)
    ctrl._dispatch_joystick_at(time.monotonic())

    assert ctrl._vx_filtered == 0.0
    assert ctrl._dx_accum == 0.0


def test_backlash_measurement_detects_camera_offset() -> None:
    pytest.importorskip("cv2")
    frame = np.zeros((160, 160, 3), dtype=np.uint8)
    frame[70:90, 70:90] = 255
    reference = center_crop(frame, 40)
    moved = np.zeros_like(frame)
    moved[70:90, 76:96] = 255

    offset = measure_offset(reference, moved, search_radius=24)

    assert offset is not None
    assert offset.dx_px == pytest.approx(6.0, abs=1.0)
    assert abs(offset.dy_px) <= 1.0
