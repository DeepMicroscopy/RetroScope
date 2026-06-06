"""Position-based tile stitching for microscope grid scans.

Note: Partially AI-generated
"""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np

# Phase-correlation responses below this are treated as "no confident match";
# the tile then keeps its nominal grid offset.
_MIN_RESPONSE = 0.05


def _frame_of(tile: dict) -> np.ndarray | None:
    frame = tile.get("frame")
    return frame if frame is not None else None


def _gray(strip: np.ndarray) -> np.ndarray:
    if strip.ndim == 3:
        strip = cv2.cvtColor(strip, cv2.COLOR_RGB2GRAY)
    return strip.astype(np.float32)


def _refine_shift(a: np.ndarray, b: np.ndarray, clamp: float) -> tuple[float, float]:
    """Sub-pixel residual that aligns overlap strip 'b' onto 'a'.

    Returns (dx, dy); (0, 0) when the two strips are too small or the correlation
    is not confident. Result is clamped to +/- 'clamp' px per axis.
    """
    if a.shape != b.shape or a.shape[0] < 4 or a.shape[1] < 4:
        return 0.0, 0.0
    ga, gb = _gray(a), _gray(b)
    try:
        window = cv2.createHanningWindow((ga.shape[1], ga.shape[0]), cv2.CV_32F)
        (dx, dy), response = cv2.phaseCorrelate(ga, gb, window)
    except cv2.error:
        return 0.0, 0.0
    if response < _MIN_RESPONSE:
        return 0.0, 0.0
    dx = float(np.clip(dx, -clamp, clamp))
    dy = float(np.clip(dy, -clamp, clamp))
    return dx, dy


def _compute_positions(
    frames: dict[tuple[int, int], np.ndarray],
    tile_w: int,
    tile_h: int,
    overlap: float,
    refine: bool,
) -> dict[tuple[int, int], tuple[int, int]]:
    stride_x = max(1, round(tile_w * (1.0 - overlap)))
    stride_y = max(1, round(tile_h * (1.0 - overlap)))
    ov_x = tile_w - stride_x
    ov_y = tile_h - stride_y
    clamp_x = max(4.0, ov_x * 0.5)
    clamp_y = max(4.0, ov_y * 0.5)

    positions: dict[tuple[int, int], tuple[int, int]] = {}
    # Row-major so left/up neighbours are already placed when we reach a tile.
    for col, row in sorted(frames, key=lambda cr: (cr[1], cr[0])):
        cur = frames[(col, row)]
        candidates: list[tuple[float, float]] = []

        left = positions.get((col - 1, row))
        if left is not None and ov_x > 0:
            lframe = frames[(col - 1, row)]
            dx, dy = (0.0, 0.0)
            if refine:
                dx, dy = _refine_shift(lframe[:, tile_w - ov_x:], cur[:, :ov_x], clamp_x)
            candidates.append((left[0] + stride_x - dx, left[1] - dy))

        up = positions.get((col, row - 1))
        if up is not None and ov_y > 0:
            uframe = frames[(col, row - 1)]
            dx, dy = (0.0, 0.0)
            if refine:
                dx, dy = _refine_shift(uframe[tile_h - ov_y:, :], cur[:ov_y, :], clamp_y)
            candidates.append((up[0] - dx, up[1] + stride_y - dy))

        if candidates:
            mx = sum(c[0] for c in candidates) / len(candidates)
            my = sum(c[1] for c in candidates) / len(candidates)
            positions[(col, row)] = (round(mx), round(my))
        else:
            positions[(col, row)] = (col * stride_x, row * stride_y)

    return positions


def _feather_weight(h: int, w: int, ov_x: int, ov_y: int) -> np.ndarray:
    """Separable linear ramp: 0 at the tile borders, 1 past the overlap width."""
    wx = np.ones(w, dtype=np.float32)
    wy = np.ones(h, dtype=np.float32)
    fx = max(1, ov_x)
    fy = max(1, ov_y)
    ramp_x = np.linspace(0.0, 1.0, fx + 1, dtype=np.float32)[1:]
    ramp_y = np.linspace(0.0, 1.0, fy + 1, dtype=np.float32)[1:]
    wx[:fx] = ramp_x
    wx[-fx:] = ramp_x[::-1]
    wy[:fy] = ramp_y
    wy[-fy:] = ramp_y[::-1]
    weight = np.outer(wy, wx)
    # Floor so a pixel covered by exactly one tile still contributes.
    return np.clip(weight, 1e-3, None)


def stitch(
    tiles: list[dict],
    overlap: float,
    refine: bool = True,
    progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    """Stitch grid tiles into a single RGB image using known positions.

    `tiles` are dicts with int 'col'/'row' and an RGB uint8 'frame'. With
    refine=False this is a plain overlap-honouring mosaic.
    """
    frames = {
        (int(t.get("col", 0)), int(t.get("row", 0))): f
        for t in tiles
        if (f := _frame_of(t)) is not None
    }
    if not frames:
        return np.zeros((1, 1, 3), dtype=np.uint8)
    if len(frames) == 1:
        return next(iter(frames.values())).copy()

    sample = next(iter(frames.values()))
    tile_h, tile_w = sample.shape[:2]
    channels = sample.shape[2] if sample.ndim == 3 else 1

    if progress:
        progress(0.1)

    positions = _compute_positions(frames, tile_w, tile_h, overlap, refine)

    if progress:
        progress(0.6)

    # Shift so the top-left of the composite is at the origin.
    min_x = min(x for x, _ in positions.values())
    min_y = min(y for _, y in positions.values())
    positions = {k: (x - min_x, y - min_y) for k, (x, y) in positions.items()}

    canvas_w = max(x for x, _ in positions.values()) + tile_w
    canvas_h = max(y for _, y in positions.values()) + tile_h

    ov_x = tile_w - max(1, round(tile_w * (1.0 - overlap)))
    ov_y = tile_h - max(1, round(tile_h * (1.0 - overlap)))
    weight = _feather_weight(tile_h, tile_w, ov_x, ov_y)

    acc = np.zeros((canvas_h, canvas_w, channels), dtype=np.float32)
    wsum = np.zeros((canvas_h, canvas_w), dtype=np.float32)

    for (col, row), (x, y) in positions.items():
        frame = frames[(col, row)].astype(np.float32)
        if frame.ndim == 2:
            frame = frame[:, :, None]
        acc[y:y + tile_h, x:x + tile_w] += frame * weight[:, :, None]
        wsum[y:y + tile_h, x:x + tile_w] += weight

    if progress:
        progress(0.9)

    wsum[wsum == 0.0] = 1.0
    out = acc / wsum[:, :, None]
    np.clip(out, 0, 255, out=out)
    out = out.astype(np.uint8)
    if channels == 1:
        out = out[:, :, 0]
    return out
