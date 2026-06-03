"""Saving rendered measurement overlays as capture files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np

from retroscope.services import ome_tiff


class MeasurementCaptureService:
    """Persists measurement images as OME-TIFF snapshots."""

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or Path.home() / "retroscope" / "captures" / "measurements"

    def save_qimage(
        self,
        image: object,
        *,
        objective: str,
        position: tuple[int, int, int],
    ) -> str:
        """Save a Qt image and return its path or an empty string on failure."""
        from PySide6.QtGui import QImage

        if not isinstance(image, QImage):
            return ""

        captured_at = datetime.now()
        path = self._new_measurement_path(captured_at)
        frame = self._qimage_to_rgb_array(image)
        width = int(image.width())
        height = int(image.height())
        x, y, z = position
        metadata = {
            "version": 1,
            "type": "snapshot",
            "captured_at": captured_at.isoformat(timespec="seconds"),
            "objective": objective,
            "position": {"x": int(x), "y": int(y), "z": int(z)},
            "width": width,
            "height": height,
            "resolution": {"width": width, "height": height},
            "format": "OME-TIFF",
            "tags": ["measurement"],
        }

        try:
            ome_tiff.write_snapshot(path, frame, metadata)
        except Exception:
            return ""
        return str(path)

    def _new_measurement_path(self, captured_at: datetime) -> Path:
        name = f"measure_{captured_at.strftime('%Y%m%d_%H%M%S_%f')[:22]}.ome.tiff"
        path = self._output_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _qimage_to_rgb_array(image) -> np.ndarray:
        from PySide6.QtGui import QImage

        rgb = image.convertToFormat(QImage.Format.Format_RGB888)
        width = rgb.width()
        height = rgb.height()
        bytes_per_line = rgb.bytesPerLine()
        raw = np.frombuffer(rgb.bits(), dtype=np.uint8).reshape(height, bytes_per_line)
        packed = raw[:, : width * 3]
        return np.ascontiguousarray(packed.reshape(height, width, 3))
