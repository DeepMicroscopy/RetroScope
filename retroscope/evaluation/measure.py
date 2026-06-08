"""Image-displacement and frame-grab helpers for the evaluation.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time

import numpy as np

from retroscope.services.backlash_measurement import center_crop, measure_offset


def _gray_f32(frame: np.ndarray):
    import cv2

    if frame.ndim == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    return frame.astype(np.float32)


def measure_shift(frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[float, float, float]:
    """Translation that maps frame_a onto frame_b in pixels.

    Returns (dx, dy, response) via cv2.phaseCorrelate with a Hanning window.
    """
    
    import cv2

    ga, gb = _gray_f32(frame_a), _gray_f32(frame_b)
    if ga.shape != gb.shape or ga.shape[0] < 8 or ga.shape[1] < 8:
        return 0.0, 0.0, 0.0
    window = cv2.createHanningWindow((ga.shape[1], ga.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(ga, gb, window)
    return float(dx), float(dy), float(response)


def measure_shift_template(
    frame_a: np.ndarray, frame_b: np.ndarray, crop: int = 96, search_radius: int = 64
) -> tuple[float, float, float] | None:
    """Cross-check displacement using template matching of the centre crop of frame_a within frame_b."""

    ref = center_crop(frame_a, size=crop)
    if ref is None:
        return None
    off = measure_offset(ref, frame_b, search_radius=search_radius)
    if off is None:
        return None
    return off.dx_px, off.dy_px, off.score


def displacement_px(frame_a: np.ndarray, frame_b: np.ndarray) -> tuple[float, float, float]:
    dx, dy, _ = measure_shift(frame_a, frame_b)
    return float(np.hypot(dx, dy)), dx, dy


def px_to_um(px: float, um_per_pixel: float) -> float:
    return float(px) * float(um_per_pixel)


def grab_frame(camera_svc, *, native: bool = False, fresh: bool = True, timeout_s: float = 2.0):
    """Return one RGB frame from the live camera service."""

    if native and hasattr(camera_svc, "capture_native_frame"):
        arr = camera_svc.capture_native_frame(allow_tap_fallback=True)
        if arr is not None:
            return np.asarray(arr)
    deadline = time.monotonic() + timeout_s
    while True:
        frame = camera_svc.get_latest_frame()
        if frame is not None:
            return np.asarray(frame).copy()
        if not fresh or time.monotonic() > deadline:
            return None
        time.sleep(0.02)
