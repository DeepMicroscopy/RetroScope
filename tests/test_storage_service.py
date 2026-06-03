"""Test the storage service."""

from pathlib import Path

from retroscope.services.storage_service import StorageService, StorageStats


class FakeConfig:
    def __init__(self) -> None:
        self.values = {}
        self.saved = False

    def set(self, key, value):
        self.values[key] = value

    def save(self):
        self.saved = True


class FakeStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.ensured = False
        self.cleared = False
        self.count = 3

    def capture_root(self):
        return self.root

    def ensure_directories(self):
        self.ensured = True

    def total_count(self):
        return self.count

    def clear_all(self):
        self.cleared = True
        self.count = 0


def test_storage_stats_conversions():
    stats = StorageStats(
        disk_used=1_073_741_824,
        disk_total=2_147_483_648,
        capture_count=4,
    )

    assert stats.disk_used_gb == 1
    assert stats.disk_total_gb == 2
    assert stats.disk_used_fraction == 0.5


def test_set_capture_root_persists_new_path(tmp_path):
    config = FakeConfig()
    store = FakeStore(tmp_path / "old")
    service = StorageService(config, store)

    new_root = service.set_capture_root(str(tmp_path / "new"))

    assert new_root == str(tmp_path / "new")
    assert config.values["captures.root"] == str(tmp_path / "new")
    assert config.saved
    assert store.ensured


def test_set_capture_root_ignores_blank_and_unchanged(tmp_path):
    config = FakeConfig()
    store = FakeStore(tmp_path / "captures")
    service = StorageService(config, store)

    assert service.set_capture_root("") is None
    assert service.set_capture_root(str(tmp_path / "captures")) is None
    assert config.values == {}
    assert not config.saved


def test_clear_all_captures_returns_refreshed_stats(tmp_path):
    config = FakeConfig()
    store = FakeStore(tmp_path)
    service = StorageService(config, store)

    stats = service.clear_all_captures()

    assert store.cleared
    assert stats.capture_count == 0
