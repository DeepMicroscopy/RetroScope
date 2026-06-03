"""Stage calibration helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TileStep:
    x_steps: int
    y_steps: int
    calibrated: bool


def stage_um_per_step(
    observed_pixels: float,
    um_per_pixel: float,
    motor_steps: int,
) -> float:
    """Return stage micrometers per motor step from a camera observed move."""
    steps = abs(int(motor_steps))
    if steps <= 0:
        return 0.0
    pixels = abs(float(observed_pixels))
    if pixels <= 0.0:
        return 0.0
    return pixels * max(0.001, float(um_per_pixel)) / steps


def tile_steps_for_frame(
    frame_width_px: int,
    frame_height_px: int,
    um_per_pixel: float,
    overlap: float,
    stage_um_per_step_x: float,
    stage_um_per_step_y: float,
) -> TileStep:
    """Compute motor steps between adjacent tiles."""

    width = max(1, int(frame_width_px))
    height = max(1, int(frame_height_px))
    ov = max(0.0, min(0.95, float(overlap)))
    move_fraction = 1.0 - ov

    sx = float(stage_um_per_step_x)
    sy = float(stage_um_per_step_y)
    scale = max(0.001, float(um_per_pixel))
    x_um = width * scale * move_fraction
    y_um = height * scale * move_fraction

    # If calibration is missing, use a fallback based on frame size.
    fallback_x = max(1, int(round(width * move_fraction)))
    fallback_y = max(1, int(round(height * move_fraction)))
    x_steps = max(1, int(round(x_um / sx))) if sx > 0.0 else fallback_x
    y_steps = max(1, int(round(y_um / sy))) if sy > 0.0 else fallback_y
    return TileStep(x_steps=x_steps, y_steps=y_steps, calibrated=sx > 0.0 or sy > 0.0)
