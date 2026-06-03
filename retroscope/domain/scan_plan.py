"""Tile-scan planning helpers."""

from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class TileStep:
    x: int
    y: int

@dataclass(frozen=True, slots=True)
class VideoScanSegment:
    dx: int
    dy: int
    tile_equivalent: int

def serpentine_order(cols: int, rows: int) -> list[tuple[int, int]]:
    """Return tile coordinates visited row-by-row, reversing every other row."""  
    order: list[tuple[int, int]] = []
    for row in range(rows):
        col_range = range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
        for col in col_range:
            order.append((col, row))
    return order

def raster_order(cols: int, rows: int) -> list[tuple[int, int]]:
    """Return tile coordinates visited left-to-right for every row."""
    return [(col, row) for row in range(rows) for col in range(cols)]

def tile_order(cols: int, rows: int, pattern: str) -> list[tuple[int, int]]:
    """Return the tile order, raster fallback."""
    if pattern == "serpentine":
        return serpentine_order(cols, rows)
    return raster_order(cols, rows)

def tile_step(
    um_per_pixel: float,
    overlap: float,
    frame_width_px: int = 1280,
    frame_height_px: int = 720,
    stage_um_per_step_x: float = 0.0,
    stage_um_per_step_y: float = 0.0,
) -> TileStep:
    """Compute XY stage steps between neighboring tiles.

    When stage scale is calibrated, X and Y are converted independently because
    the mechanical scale can differ per axis. If stage calibration is missing, 
    fallback to a coarse pixel-step: Treat one motor step as one image pixel.
    """
    safe_um_per_pixel = max(float(um_per_pixel), 0.001)
    frame_w_um = float(frame_width_px) * safe_um_per_pixel
    frame_h_um = float(frame_height_px) * safe_um_per_pixel
    step_x_um = frame_w_um * (1.0 - overlap)
    step_y_um = frame_h_um * (1.0 - overlap)
    sx = float(stage_um_per_step_x)
    sy = float(stage_um_per_step_y)
    fallback_x = max(1, int(step_x_um / safe_um_per_pixel))
    fallback_y = max(1, int(step_y_um / safe_um_per_pixel))
    x_steps = max(1, int(round(step_x_um / sx))) if sx > 0.0 else fallback_x
    y_steps = max(1, int(round(step_y_um / sy))) if sy > 0.0 else fallback_y
    return TileStep(x=x_steps, y=y_steps)

def video_scan_segments(
    cols: int,
    rows: int,
    pattern: str,
    step_x: int,
    step_y: int,
) -> list[VideoScanSegment]:
    """Return continuous row moves for video tile scanning."""
    segments: list[VideoScanSegment] = []
    if cols <= 1 and rows <= 1:
        return segments
    if cols <= 1:
        segments.append(VideoScanSegment(0, 0, 1))
        for _row in range(rows - 1):
            segments.append(VideoScanSegment(0, step_y, 1))
        return segments

    if pattern == "serpentine":
        direction = 1
        for row in range(rows):
            segments.append(
                VideoScanSegment(direction * step_x * (cols - 1), 0, cols)
            )
            if row < rows - 1:
                segments.append(VideoScanSegment(0, step_y, 0))
                direction *= -1
    else:
        for row in range(rows):
            segments.append(VideoScanSegment(step_x * (cols - 1), 0, cols))
            if row < rows - 1:
                segments.append(VideoScanSegment(-step_x * (cols - 1), step_y, 0))
    return segments
