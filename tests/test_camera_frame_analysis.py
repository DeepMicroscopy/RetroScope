"""Tests for camera frame analysis, focus scores and analysis gating.

Note: Partially AI-generated
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.bridge.direct_camera_bridge import DirectCameraBridge
from retroscope.domain.focus_metrics import grayscale_focus_score
from retroscope.services.camera_service import CameraService


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class FakeConfig:
    def __init__(self) -> None:
        self.values = {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value


class FakeFrame:
    def __init__(self, width: int = 640, height: int = 360) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


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

    def convert_frame(received_frame: object, compute_focus: bool = True):
        conversions.append(received_frame)
        return analysis_frame, None

    monkeypatch.setattr(bridge, "_frame_to_rgb_array_and_focus", convert_frame)
    monkeypatch.setattr(bridge, "_copy_focus_plane_from_frame", lambda _frame: analysis_frame[:, :, 0])
    monkeypatch.setattr(bridge, "_focus_score_from_plane", lambda _plane: 55.0)

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


def test_direct_camera_bridge_taps_frames_for_fallback_recording_when_analysis_disabled() -> None:
    _app()

    class FakeCameraService:
        def needs_recording_frame_tap(self) -> bool:
            return True

    service = FakeCameraService()
    bridge = DirectCameraBridge(service, enabled=True)
    bridge.setFrameAnalysisEnabled(False)
    calls: list[tuple[object, object]] = []
    bridge._enqueue_analysis_frame = lambda frame, focus: calls.append((frame, focus))

    try:
        frame = FakeFrame()
        bridge._on_video_frame(frame)

        assert calls == [(frame, None)]
    finally:
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
    _app()
    service = CameraService(FakeConfig())

    expected = [30.0, 30.0, 32.0, 32.0, 4100.0]
    inputs = [30.0, 4400.0, 32.0, 4200.0, 4100.0]
    observed: list[float] = []
    for value in inputs:
        service.on_focus_score_ready(value)
        observed.append(service._latest_source_focus_score or 0.0)

    assert observed == pytest.approx(expected)
