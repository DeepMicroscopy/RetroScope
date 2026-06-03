"""Test the gallery store and bridge logic."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

from retroscope.services import ome_tiff
from retroscope.services.image_store import ImageStore

try:
    from PySide6.QtCore import QCoreApplication
    from retroscope.bridge.gallery_bridge import GalleryBridge
    HAS_QT = True
except ModuleNotFoundError:
    HAS_QT = False


class FakeMotion:
    def __init__(self) -> None:
        self.xy_moves: list[tuple[int, int, int]] = []
        self.z_moves: list[int] = []

    def move_rel(self, dx: int, dy: int, dz: int) -> None:
        self.xy_moves.append((dx, dy, dz))

    def move_z(self, dz: int) -> None:
        self.z_moves.append(dz)


class FakeObjective:
    def __init__(self) -> None:
        self.active: list[str] = []

    def set_active(self, name: str) -> None:
        self.active.append(name)


class FakeConfig:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._data = {}

    def get(self, key: str, default=None):
        if key == "captures.root":
            return str(self._root)
        if key in self._data:
            return self._data[key]
        return default

    def set(self, key: str, value) -> None:
        self._data[key] = value


def _mk_ome(path: Path, color: str = "green", metadata: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.new("RGB", (32, 24), color=color))
    ome_tiff.write_snapshot(
        path,
        rgb,
        {
            "version": 1,
            "type": "snapshot",
            "captured_at": "2026-04-13T10:11:12",
            "objective": "",
            "position": {"x": 0, "y": 0, "z": 0},
            "width": 32,
            "height": 24,
            "format": "OME-TIFF",
            "tags": [],
            **(metadata or {}),
        },
    )


def _mk_avi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"FAKE_AVI")


def _store(tmp_path: Path) -> ImageStore:
    cfg = FakeConfig(tmp_path / "captures")
    return ImageStore(cfg)


def test_ome_tiff_and_video_metadata_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snap = store.snapshot_dir() / "a.ome.tiff"
    vid = store.video_dir() / "b.avi"

    _mk_ome(snap)
    _mk_avi(vid)

    snap_md = {
        "version": 1,
        "type": "snapshot",
        "captured_at": "2026-04-13T10:11:12",
        "objective": "20x",
        "position": {"x": 100, "y": 200, "z": 300},
        "width": 32,
        "height": 24,
        "tags": ["cell"],
    }
    vid_md = {
        "version": 1,
        "type": "video",
        "captured_at": "2026-04-13T10:11:12",
        "objective": "10x",
        "position": {"x": 1, "y": 2, "z": 3},
        "width": 1280,
        "height": 720,
        "tags": ["timelapse"],
    }

    assert store.write_metadata(snap, snap_md)
    assert store.write_metadata(vid, vid_md)

    assert store.read_metadata(snap)["objective"] == "20x"
    assert store.read_metadata(snap)["tags"] == ["cell"]
    assert store.read_metadata(vid)["type"] == "video"
    assert store.read_metadata(vid)["width"] == 1280


def test_scan_and_delete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snap = store.snapshot_dir() / "s1.ome.tiff"
    vid = store.video_dir() / "v1.avi"

    _mk_ome(snap)
    _mk_avi(vid)

    assert store.write_metadata(snap, {
        "version": 1,
        "type": "snapshot",
        "captured_at": "2026-04-13T12:00:00",
        "position": {"x": 10, "y": 20, "z": 30},
        "tags": ["a"],
    })
    assert store.write_metadata(vid, {
        "version": 1,
        "type": "video",
        "captured_at": "2026-04-13T12:10:00",
        "position": {"x": 11, "y": 21, "z": 31},
        "tags": ["b"],
    })

    items = store.scan_items()
    types = sorted(i["type"] for i in items)
    assert types == ["snapshot", "video"]

    assert store.persist_tags(snap, ["x", "y"])
    assert store.read_metadata(snap)["tags"] == ["x", "y"]

    assert store.delete_item(vid)
    assert not vid.exists()
    assert not store.sidecar_path(vid).exists()


def test_naming_pattern_expands_type_and_avoids_collisions(tmp_path: Path) -> None:
    cfg = FakeConfig(tmp_path / "captures")
    cfg.set("camera.naming_pattern", "{date}_{time}_{obj}")
    store = ImageStore(cfg)
    captured = datetime(2026, 5, 5, 12, 34, 56)

    first = store.new_image_path("snapshot", "capture", objective="40x oil", captured_at=captured)
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_bytes(b"x")
    second = store.new_image_path("snapshot", "capture", objective="40x oil", captured_at=captured)

    assert first.name == "20260505_123456_40x_oil_capture.ome.tiff"
    assert second.name == "20260505_123456_40x_oil_capture_002.ome.tiff"


def test_naming_pattern_seq_token_controls_collision_suffix(tmp_path: Path) -> None:
    cfg = FakeConfig(tmp_path / "captures")
    cfg.set("camera.naming_pattern", "{type}_{seq}")
    store = ImageStore(cfg)
    captured = datetime(2026, 5, 5, 12, 34, 56)

    first = store.new_image_path("stack", "stack", captured_at=captured)
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_bytes(b"x")
    second = store.new_image_path("stack", "stack", captured_at=captured)

    assert first.name == "stack_001.ome.tiff"
    assert second.name == "stack_002.ome.tiff"


def test_gallery_bridge_filter_sort_group_and_goto(tmp_path: Path) -> None:
    if not HAS_QT:
        try:
            import pytest

            pytest.skip("PySide6 not installed")
        except ModuleNotFoundError:
            return
    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None

    store = _store(tmp_path)
    now = datetime.now().replace(microsecond=0)
    yesterday = now - timedelta(days=1)

    snap_new = store.snapshot_dir() / "new.ome.tiff"
    snap_old = store.snapshot_dir() / "old.ome.tiff"
    vid = store.video_dir() / "video.avi"

    _mk_ome(snap_new, "red")
    _mk_ome(snap_old, "blue")
    _mk_avi(vid)

    assert store.write_metadata(snap_new, {
        "version": 1,
        "type": "snapshot",
        "captured_at": now.isoformat(),
        "objective": "40x",
        "position": {"x": 1000, "y": 2000, "z": 300},
        "tags": ["new"],
    })
    assert store.write_metadata(snap_old, {
        "version": 1,
        "type": "snapshot",
        "captured_at": yesterday.isoformat(),
        "objective": "10x",
        "position": {"x": 100, "y": 200, "z": 30},
        "tags": ["old"],
    })
    assert store.write_metadata(vid, {
        "version": 1,
        "type": "video",
        "captured_at": now.isoformat(),
        "objective": "20x",
        "position": {"x": 500, "y": 600, "z": 70},
        "tags": ["clip"],
    })

    motion = FakeMotion()
    objective = FakeObjective()
    bridge = GalleryBridge(
        store,
        motion,
        objective,
        get_position=lambda: (900, 1900, 250),
    )

    assert bridge.captureCount == 3
    assert len(bridge.groupedItems) >= 2

    first_newest = bridge.items[0]["id"]
    bridge.setSortOrder("oldest")
    first_oldest = bridge.items[0]["id"]
    assert first_newest != first_oldest

    bridge.setFilterType("video")
    assert bridge.captureCount == 1
    assert bridge.items[0]["type"] == "video"

    bridge.setFilterType("all")
    bridge.selectItem(str(snap_new.resolve()))
    bridge.goToSelectedPosition()

    assert objective.active[-1] == "40x"
    assert motion.xy_moves[-1] == (100, 100, 0)
    assert motion.z_moves[-1] == 50
