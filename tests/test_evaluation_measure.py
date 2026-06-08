"""Evaluation: image-displacement measurement."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("cv2")

from retroscope.evaluation import measure


def _textured(h=128, w=160):
    rng = np.random.default_rng(7)
    base = rng.integers(0, 255, size=(h, w), dtype=np.uint8)
    return np.stack([base, base, base], axis=-1)


def test_measure_shift_recovers_known_translation():
    a = _textured()
    shift_x, shift_y = 5, -3
    b = np.roll(np.roll(a, shift_x, axis=1), shift_y, axis=0)
    dx, dy, resp = measure.measure_shift(a, b)
    assert resp > 0.2
    assert abs(abs(dx) - abs(shift_x)) <= 1.0
    assert abs(abs(dy) - abs(shift_y)) <= 1.0


def test_displacement_magnitude():
    a = _textured()
    b = np.roll(a, 8, axis=1)
    mag, dx, dy = measure.displacement_px(a, b)
    assert abs(mag - 8) <= 1.5


def test_px_to_um():
    assert measure.px_to_um(10, 0.5) == 5.0


def test_template_cross_check():
    a = _textured()
    b = np.roll(a, 6, axis=1)
    res = measure.measure_shift_template(a, b, crop=64, search_radius=32)
    assert res is not None
    dx, dy, score = res
    assert abs(abs(dx) - 6) <= 1.5
    assert score > 0.3
