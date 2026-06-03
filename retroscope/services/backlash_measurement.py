"""Camera-assisted backlash measurement helpers.

Note: Partially AI-generated (measure_offset)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BacklashOffset:
    dx_px: float
    dy_px: float
    score: float


def center_crop(frame: np.ndarray, size: int = 96) -> np.ndarray | None:
    """Return a square crop from the frame centre."""
    if frame is None or frame.ndim < 2:
        return None
    h, w = frame.shape[:2]
    side = max(16, min(int(size), h, w))
    x0 = max(0, (w - side) // 2)
    y0 = max(0, (h - side) // 2)
    crop = frame[y0:y0 + side, x0:x0 + side]
    if crop.size == 0:
        return None
    return np.ascontiguousarray(crop)


def measure_offset(
    reference_crop: np.ndarray,
    frame: np.ndarray,
    search_radius: int = 48,
) -> BacklashOffset | None:
    """Find the reference crop near the centre of the current frame."""
    try:
        import cv2
    except Exception:
        return None
    if reference_crop is None or frame is None:
        return None
    if reference_crop.ndim == 3:
        ref = cv2.cvtColor(reference_crop, cv2.COLOR_RGB2GRAY)
    else:
        ref = reference_crop
    h, w = frame.shape[:2]
    th, tw = ref.shape[:2]
    if th <= 4 or tw <= 4 or h < th or w < tw:
        return None

    cx = w // 2
    cy = h // 2
    radius = max(4, int(search_radius))
    x0 = max(0, cx - tw // 2 - radius)
    y0 = max(0, cy - th // 2 - radius)
    x1 = min(w, cx + tw // 2 + radius)
    y1 = min(h, cy + th // 2 + radius)
    search = frame[y0:y1, x0:x1]
    if search.shape[0] < th or search.shape[1] < tw:
        return None
    if search.ndim == 3:
        search_gray = cv2.cvtColor(search, cv2.COLOR_RGB2GRAY)
    else:
        search_gray = search

    result = cv2.matchTemplate(search_gray, ref, cv2.TM_CCOEFF_NORMED)
    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
    match_x = x0 + max_loc[0] + tw / 2.0
    match_y = y0 + max_loc[1] + th / 2.0
    return BacklashOffset(
        dx_px=float(match_x - cx),
        dy_px=float(match_y - cy),
        score=float(max_val),
    )
