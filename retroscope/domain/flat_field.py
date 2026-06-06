"""Flat-field (vignette / shading) correction for tile scans.

Note: Partially AI-generated
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Pixels in the reference below this fraction of the mean are treated as the floor
# value, so dark dust specks / dead pixels can't blow up into huge gains.
_MIN_GAIN_FRACTION = 0.1


def normalize_reference(flat: np.ndarray) -> np.ndarray:
    """Turn a raw reference frame into a per-channel gain map with mean ~1.0.

    Computed per channel so a colored illumination tint is preserved rather than
    being baked into the correction.
    """
    gain = flat.astype(np.float32)
    if gain.ndim == 2:
        gain = gain[:, :, None]

    flat_mean = gain.mean(axis=(0, 1), keepdims=True)
    flat_mean[flat_mean <= 0.0] = 1.0
    gain = gain / flat_mean

    # Clamp dark outliers so 1/gain stays bounded.
    np.clip(gain, _MIN_GAIN_FRACTION, None, out=gain)
    return gain


def apply_flat_field(tile: np.ndarray, gain: np.ndarray) -> np.ndarray:
    """Divide a tile by the normalized gain map, returning a uint8 image.

    Falls back to the input unchanged if the gain map shape does not match the
    tile (e.g. a reference captured at a different resolution).
    """
    if gain is None:
        return tile

    g = gain
    if g.ndim == 3 and g.shape[2] == 1 and tile.ndim == 3:
        g = np.broadcast_to(g, tile.shape)
    if g.shape[:2] != tile.shape[:2]:
        return tile

    corrected = tile.astype(np.float32) / g
    np.clip(corrected, 0, 255, out=corrected)
    return corrected.astype(np.uint8)


def save_reference(path: str | Path, frame: np.ndarray) -> None:
    """Persist a raw reference frame as a .npy next to the config."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, frame)


def load_reference(path: str | Path) -> np.ndarray | None:
    """Load a saved reference frame, or None if it doesn't exist / can't be read."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        return np.load(path)
    except Exception:
        return None
