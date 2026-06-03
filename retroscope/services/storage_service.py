"""Storage service: For capture settings and disk statistics."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StorageStats:
    disk_used: int
    disk_total: int
    capture_count: int

    @property
    def disk_used_gb(self) -> float:
        return self.disk_used / 1_073_741_824.0

    @property
    def disk_total_gb(self) -> float:
        return max(0.001, self.disk_total / 1_073_741_824.0)

    @property
    def disk_used_fraction(self) -> float:
        return min(1.0, self.disk_used / max(1, self.disk_total))


class StorageService:
    """Coordinate capture storage settings and storage statistics."""

    def __init__(self, config, image_store) -> None:
        self._config = config
        self._store = image_store

    def capture_root(self) -> Path:
        return self._store.capture_root()

    def set_capture_root(self, value: str) -> str | None:
        clean = str(value).strip()
        if clean == "":
            return None

        expanded = str(Path(clean).expanduser())
        if expanded == str(self._store.capture_root()):
            return None

        self._config.set("captures.root", expanded)
        self._config.save()
        self._store.ensure_directories()
        return expanded

    def refresh_stats(self) -> StorageStats:
        try:
            usage = shutil.disk_usage(self._store.capture_root())
            disk_used = int(usage.used)
            disk_total = max(1, int(usage.total))
        except Exception:
            disk_used = 0
            disk_total = 1

        try:
            capture_count = int(self._store.total_count())
        except Exception:
            capture_count = 0

        return StorageStats(
            disk_used=disk_used,
            disk_total=disk_total,
            capture_count=capture_count,
        )

    def clear_all_captures(self) -> StorageStats:
        self._store.clear_all()
        return self.refresh_stats()
