"""Tests for automation bridge task labels and completion details."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.bridge.automation_bridge import AutomationBridge


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class SignalStub:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class FakeFocusStacker:
    def __init__(self) -> None:
        self.paused_changed = SignalStub()
        self.frame_captured = SignalStub()
        self.progress = SignalStub()
        self.finished = SignalStub()
        self.busy = False

    def start(self, **_kwargs) -> None:
        self.busy = True

    def cancel(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass


class FakeTileScanner:
    def __init__(self) -> None:
        self.paused_changed = SignalStub()
        self.tile_done = SignalStub()
        self.progress = SignalStub()
        self.finished = SignalStub()
        self.stitch_started = SignalStub()
        self.stitch_progress = SignalStub()
        self.stitch_finished = SignalStub()
        self.busy = False
        self.start_args = None

    def start(self, *args) -> None:
        self.busy = True
        self.start_args = args

    def cancel(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass


def _bridge() -> tuple[AutomationBridge, FakeTileScanner]:
    _app()
    tile_scanner = FakeTileScanner()
    return AutomationBridge(FakeFocusStacker(), tile_scanner), tile_scanner


def test_tile_scan_mosaic_mode_uses_mosaic_labels() -> None:
    bridge, tile_scanner = _bridge()

    bridge.startTileScan(2, 1, 0.2, "raster", False, False, False, 1000)
    tile_scanner.stitch_started.emit()
    tile_scanner.finished.emit()

    assert tile_scanner.start_args == (2, 1, 0.2, "raster", False, False, False, 1000)
    assert bridge.completedTasks[0]["name"] == "Saving mosaic…"
    assert bridge.completedTasks[0]["detail"] == "Grid mosaic saved"


def test_tile_scan_stitch_mode_waits_for_stitch_finished_label() -> None:
    bridge, tile_scanner = _bridge()

    bridge.startTileScan(2, 1, 0.2, "raster", False, False, True, 1000)
    tile_scanner.stitch_started.emit()
    tile_scanner.finished.emit()

    assert bridge.busy is True
    assert bridge.taskName == "Stitching…"
    assert bridge.completedTasks == []

    tile_scanner.stitch_finished.emit("scan.ome.tiff")

    assert bridge.busy is False
    assert bridge.completedTasks[0]["name"] == "Stitching…"
    assert bridge.completedTasks[0]["detail"] == "Scan saved"


def test_tile_scan_video_mode_ignores_stitch_detail() -> None:
    bridge, tile_scanner = _bridge()

    bridge.startTileScan(2, 1, 0.2, "raster", False, True, True, 1000)
    tile_scanner.finished.emit()

    assert tile_scanner.start_args == (2, 1, 0.2, "raster", False, True, True, 1000)
    assert bridge.completedTasks[0]["detail"] == "video recorded"
