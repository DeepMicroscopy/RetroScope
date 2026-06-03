"""Helpers for objective calibration workflows."""

from __future__ import annotations

import math

DOF_UNSET_Z = -2_147_483_648

def normalized_distance_px(
    image_width: float,
    image_height: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    """Return pixel distance between two normalized image coordinates."""
    width = max(1.0, float(image_width))
    height = max(1.0, float(image_height))
    dx = (float(x2) - float(x1)) * width
    dy = (float(y2) - float(y1)) * height
    return math.hypot(dx, dy)

def um_per_pixel(real_um: float, pixel_distance: float) -> float:
    if real_um <= 0 or pixel_distance <= 0:
        return 0.0
    return float(real_um) / float(pixel_distance)

def dof_steps_between(upper_z: int, lower_z: int) -> int:
    if upper_z == DOF_UNSET_Z or lower_z == DOF_UNSET_Z:
        return 0
    return abs(int(upper_z) - int(lower_z))

def suggested_focus_stack_step(dof_steps: int) -> int:
    return max(1, math.floor(int(dof_steps) / 2 + 0.5))

def adjusted_backlash_steps(current: int, delta: int, minimum: int = 0, maximum: int = 150) -> int:
    return max(int(minimum), min(int(maximum), int(current) + int(delta)))
