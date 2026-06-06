"""Tests for camera-based backlash measurement helpers."""

from __future__ import annotations

import numpy as np
import pytest

from retroscope.services.backlash_measurement import center_crop, measure_offset


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
