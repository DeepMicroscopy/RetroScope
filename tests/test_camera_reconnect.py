"""Tests for camera reconnect."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QObject, Signal


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class ConfigStub:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value):
        self.values[key] = value


class FakeButtons(QObject):
    button_pressed = Signal(int)


class FakeVideoSink:
    def setVideoFrame(self, _frame: object) -> None:
        pass


class NullDevice:
    def isNull(self) -> bool:
        return True


def test_button_manager_suppresses_startup_and_camera_change_edges(monkeypatch) -> None:
    _app()
    import retroscope.services.button_manager as button_manager
    from retroscope.services.button_manager import ButtonManager

    now = 100.0
    monkeypatch.setattr(button_manager.time, "monotonic", lambda: now)

    driver = FakeButtons()
    manager = ButtonManager(driver, ConfigStub({"buttons.mapping": ["autofocus"]}))
    seen: list[str] = []
    manager.register_action("autofocus", "Autofocus", lambda: seen.append("af"))

    driver.button_pressed.emit(0)
    assert seen == []

    now = 102.0
    driver.button_pressed.emit(0)
    assert seen == ["af"]

    manager.suppress_for(1.0)
    driver.button_pressed.emit(0)
    assert seen == ["af"]

    now = 103.1
    driver.button_pressed.emit(0)
    assert seen == ["af", "af"]


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
        assert service.disconnects >= 1
    finally:
        bridge.stop()
