"""Focus-stack blending algorithms. Used by FocusStackerService."""

from __future__ import annotations

import numpy as np
import cv2

DEFAULT_PYRAMID_LEVELS = 6

def laplacian_map(frame: np.ndarray) -> np.ndarray:
    """Per-pixel absolute Laplacian of an RGB frame's grayscale."""
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    return np.abs(cv2.Laplacian(gray, cv2.CV_32F))

def max_selection_blend(frames: list[np.ndarray]) -> np.ndarray:
    """Per-pixel: Pick the frame with the highest local Lapalcian."""
    maps = np.stack([laplacian_map(f) for f in frames], axis=0)
    best = np.argmax(maps, axis=0)
    stack = np.stack(frames, axis=0)
    h, w = best.shape
    return stack[best, np.arange(h)[:, None], np.arange(w)[None, :]]

def pyramid_blend(
    frames: list[np.ndarray],
    levels: int = DEFAULT_PYRAMID_LEVELS,
) -> np.ndarray:
    """Laplacian pyramid blend weight by per-sharpness."""
    n = len(frames)
    lp_pyrs: list[list[np.ndarray]] = []
    w_pyrs:  list[list[np.ndarray]] = []

    for frame in frames:
        f32 = frame.astype(np.float32)

        # Gaussian pyramid
        gp = [f32]
        for _ in range(levels):
            gp.append(cv2.pyrDown(gp[-1]))

        # Laplacian pyramid
        lp: list[np.ndarray] = []
        for i in range(levels):
            up = cv2.pyrUp(gp[i + 1], dstsize=(gp[i].shape[1], gp[i].shape[0]))
            lp.append(gp[i] - up)
        lp.append(gp[levels])  # coarsest level is the Gaussian base
        lp_pyrs.append(lp)

        # Weight pyramid: abs Laplacian of grayscale at each scale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY).astype(np.float32)
        gp_g = [gray]
        for _ in range(levels):
            gp_g.append(cv2.pyrDown(gp_g[-1]))
        wp: list[np.ndarray] = [np.abs(cv2.Laplacian(g, cv2.CV_32F)) for g in gp_g]
        w_pyrs.append(wp)

    # Blend each pyramid level
    blended_pyr: list[np.ndarray] = []
    for lvl in range(levels + 1):
        w_stack = np.stack([w_pyrs[i][lvl] for i in range(n)], axis=0)        # (N, H, W)
        norm_w = w_stack / (w_stack.sum(axis=0, keepdims=True) + 1e-6)
        lp_stack = np.stack([lp_pyrs[i][lvl] for i in range(n)], axis=0)      # (N, H, W, 3)
        blended_pyr.append((lp_stack * norm_w[:, :, :, np.newaxis]).sum(axis=0))

    # Reconstruct from blended pyramid
    result = blended_pyr[levels]
    for lvl in range(levels - 1, -1, -1):
        result = cv2.pyrUp(result, dstsize=(blended_pyr[lvl].shape[1], blended_pyr[lvl].shape[0]))
        result = result + blended_pyr[lvl]

    return np.clip(result, 0, 255).astype(np.uint8)
