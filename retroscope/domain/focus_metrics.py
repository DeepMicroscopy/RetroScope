"""Focus-score measurement for autofocus, previews and the focus badge.

References for the focus operators used:
- Pech-Pacheco et al., "Diatom autofocusing in brightfield microscopy: a comparative study", 2000
- Pertuz et al., "Analysis of focus measure operators for shape-from-focus", Pattern Recognition, 2013
- Scharr, "Optimale Operatoren in der Digitalen Bildverarbeitung", Univ. Heidelberg, 2000

Note: Partially AI-generated
"""

from __future__ import annotations

import numpy as np
import cv2

def _crop_by_roi(gray: np.ndarray, roi: float) -> np.ndarray:
    if roi <= 0.0:
        return gray
    h, w = gray.shape[:2]
    cropped = gray[int(h * roi):int(h * (1 - roi)), int(w * roi):int(w * (1 - roi))]
    return cropped if cropped.size > 0 else gray

def laplacian_variance(frame: np.ndarray, roi: float = 0.33) -> float:
    """Laplacian variance over the centre crop of an RGB frame.

    Higher values indicate sharper images. 'roi' is the fraction trimmed
    from each side (0.33 -> keep center third).
    """
    h, w = frame.shape[:2]
    crop = frame[int(h * roi):int(h * (1 - roi)), int(w * roi):int(w * (1 - roi))]
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    return grayscale_focus_score(gray, roi=0.0)


def grayscale_laplacian_variance(gray: np.ndarray, roi: float = 0.33) -> float:
    """Laplacian variance over a grayscale frame or crop."""
    gray = _crop_by_roi(gray, roi)
    if gray.size == 0:
        return 0.0
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def grayscale_focus_score(gray: np.ndarray, roi: float = 0.15) -> float:
    """Focus score from multiple luma sharpness cues.

    Uses the sharpest informative tile inside the central field so a blank
    centre point does not flatten the whole focus meter. A light blur is applied before 
    measuring sharpness, which makes the metric much less sensitive to sensor noise than 
    raw Laplacian variance.

    It combines variance-of-Laplacian (Pech-Pacheco et al., 2000) with OpenCV's Scharr.
    Scharr optimized derivative kernels improve rotational accuracy for 3x3 gradients (Scharr, 2000).

    The contrast gate and tile pooling are practical safeguards for microscope
    scenes with blank regions. They are motivated by the known dependence of
    focus measures on texture, contrast, noise and window size discussed by Pertuz et al. (2013).
    """
    gray = _crop_by_roi(gray, roi)
    if gray.size == 0:
        return 0.0
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)

    h, w = gray.shape[:2]
    rows = np.array_split(np.arange(h), 3)
    cols = np.array_split(np.arange(w), 3)
    scores: list[float] = []
    for ys in rows:
        for xs in cols:
            tile = gray[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
            if tile.size < 64:
                continue
            contrast = float(tile.std())
            percentile_contrast = float(np.percentile(tile, 95) - np.percentile(tile, 5))
            if contrast < 1.5 or percentile_contrast < 4.0:
                continue
            smooth = cv2.GaussianBlur(tile, (0, 0), 0.8)
            lap = float(cv2.Laplacian(smooth, cv2.CV_32F).var())
            gx = cv2.Scharr(smooth, cv2.CV_32F, 1, 0)
            gy = cv2.Scharr(smooth, cv2.CV_32F, 0, 1)
            mag2 = gx * gx + gy * gy
            high_edge_cutoff = float(np.percentile(mag2, 90))
            high_edges = mag2[mag2 >= high_edge_cutoff]
            tenengrad = float(high_edges.mean()) if high_edges.size else 0.0
            normalized_edges = tenengrad / max(8.0, percentile_contrast)
            scores.append(lap * 2.0 + normalized_edges * 0.15)

    if not scores:
        return grayscale_laplacian_variance(gray, roi=0.0)
    return float(np.percentile(scores, 80))


def parabolic_peak(
    z_left: int, s_left: float,
    z_mid: int,  s_mid: float,
    z_right: int, s_right: float,
) -> int:
    """Z position of the parabolic peak through three adjacent samples."""
    denom = float(s_left) - 2.0 * float(s_mid) + float(s_right)
    if denom >= 0.0:
        return int(z_mid)
    offset = 0.5 * (float(s_left) - float(s_right)) / denom
    # Clamp the interpolation to +/-1 sample interval
    offset = max(-1.0, min(1.0, offset))
    step = (float(z_right) - float(z_left)) / 2.0
    return int(round(float(z_mid) + offset * step))

