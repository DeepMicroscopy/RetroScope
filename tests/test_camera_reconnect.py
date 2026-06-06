"""Tests for camera reconnect."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class ConfigStub:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value


class FakeVideoSink:
    def __init__(self) -> None:
        self.frames: list[object] = []

    def setVideoFrame(self, _frame: object) -> None:
        self.frames.append(_frame)


class NullDevice:
    def isNull(self) -> bool:
        return True


class FakeFrame:
    def __init__(self, width: int = 640, height: int = 360) -> None:
        self._width = width
        self._height = height

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class FakeSignal:
    def disconnect(self, _slot) -> None:
        pass


class FakeCamera:
    errorOccurred = FakeSignal()
    activeChanged = FakeSignal()

    def stop(self) -> None:
        pass


def test_camera_disconnect_clears_stale_frames_focus_and_native_recording(tmp_path: Path) -> None:
    _app()
    from retroscope.services.camera_service import CameraService

    service = CameraService(ConfigStub())
    recording_changes: list[bool] = []
    saved_paths: list[str] = []
    service.recording_changed.connect(recording_changes.append)
    service.recording_saved.connect(saved_paths.append)

    try:
        frame = np.full((6, 8, 3), 128, dtype=np.uint8)
        service.on_frame_ready(frame)
        service.on_focus_score_ready(123.0)
        with service._lock:
            service._recording = True
            service._native_recording = True
            service._recording_path = tmp_path / "recording.mp4"
            service._recording_started_at = datetime(2026, 6, 5, 12, 0, 0)
            service._recording_started_monotonic = 1.0
            service._recording_objective = "10x"
            service._recording_position = {"x": 1, "y": 2, "z": 3}
            service._recording_dims = (1920, 1080)
        (tmp_path / "recording.mp4").write_bytes(b"video")

        service.on_camera_disconnected()

        assert service.get_latest_frame() is None
        assert service.raw_focus_status()[1] is None
        assert service.is_recording() is False
        assert recording_changes == [False]
        assert saved_paths == [str(tmp_path / "recording.mp4")]
    finally:
        service.shutdown()


def test_direct_camera_bridge_keeps_polling_when_no_video_input(monkeypatch) -> None:
    _app()
    from retroscope.bridge.direct_camera_bridge import DirectCameraBridge

    class FakeCameraService:
        def __init__(self) -> None:
            self.disconnects = 0

        def on_camera_disconnected(self) -> None:
            self.disconnects += 1

    service = FakeCameraService()
    bridge = DirectCameraBridge(service, enabled=True)
    monkeypatch.setattr(bridge, "_select_camera_device", lambda: NullDevice())

    try:
        bridge.setVideoSink(FakeVideoSink())

        assert bridge._reconnect_timer.isActive()
    finally:
        bridge.stop()


def test_direct_camera_bridge_marks_connected_on_first_valid_frame() -> None:
    _app()
    from retroscope.bridge.direct_camera_bridge import DirectCameraBridge

    service = object()
    sink = FakeVideoSink()
    bridge = DirectCameraBridge(service, enabled=True)
    bridge._output_sink = sink
    bridge.setFrameAnalysisEnabled(False)
    seen: list[bool] = []
    bridge.camera_connected_changed.connect(seen.append)
    frame = FakeFrame()

    try:
        assert bridge.cameraConnected is False

        bridge._on_video_frame(frame)

        assert bridge.cameraConnected is True
        assert seen == [True]
        assert sink.frames == [frame]
    finally:
        bridge.stop()


def test_direct_camera_bridge_watchdog_restarts_stalled_camera() -> None:
    _app()
    from retroscope.bridge.direct_camera_bridge import DirectCameraBridge

    class FakeCameraService:
        def __init__(self) -> None:
            self.disconnects = 0

        def on_camera_disconnected(self) -> None:
            self.disconnects += 1

    service = FakeCameraService()
    bridge = DirectCameraBridge(service, enabled=True)
    bridge._output_sink = FakeVideoSink()
    bridge._camera = FakeCamera()
    bridge._active_device_key = "cam"
    bridge._camera_connected = True
    bridge._camera_started_s = 1.0
    bridge._last_video_frame_s = 2.0
    bridge._video_inputs = lambda: []

    try:
        bridge._camera_watchdog_tick()

        assert bridge._camera is None
        assert bridge._reconnect_timer.isActive()
        assert service.disconnects == 1
    finally:
        bridge.stop()
