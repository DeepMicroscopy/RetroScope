"""Image-displacement and frame-grab helpers for the evaluation.

Note: Partially AI-generated.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

import numpy as np

from retroscope.services.backlash_measurement import center_crop, measure_offset


@dataclass(frozen=True)
class DisplacementResult:
    dx_px: float
    dy_px: float
    magnitude_px: float
    phase_response: float
    template_dx_px: float | None = None
    template_dy_px: float | None = None
    template_score: float | None = None
    valid: bool = True
    reason: str = ""

    def axis_px(self, axis: int) -> float:
        return abs(self.dx_px if int(axis) == 0 else self.dy_px)

    def cross_axis_px(self, axis: int) -> float:
        return abs(self.dy_px if int(axis) == 0 else self.dx_px)


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


def measure_displacement(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    *,
    axis: int | None = None,
    min_phase_response: float = 0.15,
    min_axis_px: float = 0.5,
    cross_axis_max_px: float | None = None,
    template_crop: int = 96,
    template_search_radius: int = 64,
    template_min_score: float = 0.0,
    require_template: bool = False,
) -> DisplacementResult:
    """Measure image displacement and attach validity metadata for evaluation CSVs."""

    dx, dy, response = measure_shift(frame_a, frame_b)
    template = measure_shift_template(
        frame_a,
        frame_b,
        crop=template_crop,
        search_radius=template_search_radius,
    )
    template_dx = template[0] if template is not None else None
    template_dy = template[1] if template is not None else None
    template_score = template[2] if template is not None else None

    result = DisplacementResult(
        dx_px=float(dx),
        dy_px=float(dy),
        magnitude_px=float(np.hypot(dx, dy)),
        phase_response=float(response),
        template_dx_px=template_dx,
        template_dy_px=template_dy,
        template_score=template_score,
    )

    reasons: list[str] = []
    if result.phase_response < float(min_phase_response):
        reasons.append("low_phase_response")
    if axis is not None and result.axis_px(axis) < float(min_axis_px):
        reasons.append("axis_displacement_too_small")
    if (
        axis is not None
        and cross_axis_max_px is not None
        and result.cross_axis_px(axis) > float(cross_axis_max_px)
    ):
        reasons.append("cross_axis_displacement_too_large")
    if require_template and template_score is None:
        reasons.append("template_missing")
    if template_score is not None and template_score < float(template_min_score):
        reasons.append("low_template_score")

    if reasons:
        return DisplacementResult(
            dx_px=result.dx_px,
            dy_px=result.dy_px,
            magnitude_px=result.magnitude_px,
            phase_response=result.phase_response,
            template_dx_px=result.template_dx_px,
            template_dy_px=result.template_dy_px,
            template_score=result.template_score,
            valid=False,
            reason=";".join(reasons),
        )
    return result


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


def grab_fresh(camera_svc, *, discard: int = 1, timeout_s: float = 5.0):
    waiter = getattr(camera_svc, "wait_for_next_frame", None)
    if waiter is None:
        f = camera_svc.get_latest_frame()
        return np.asarray(f).copy() if f is not None else None
    frame = None
    for _ in range(max(1, discard + 1)):
        f = waiter(timeout=timeout_s)
        if f is None:
            break
        frame = np.asarray(f).copy()
    if frame is None:
        f = camera_svc.get_latest_frame()
        return np.asarray(f).copy() if f is not None else None
    return frame.copy()
