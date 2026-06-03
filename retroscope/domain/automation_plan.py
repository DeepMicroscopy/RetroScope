"""Helpers for automation previews and task calc."""

from __future__ import annotations

def focus_stack_total_steps(z_start: int, z_end: int) -> int:
    return abs(int(z_end) - int(z_start))

def focus_stack_frame_count(z_start: int, z_end: int, step_size: int) -> int:
    total_steps = focus_stack_total_steps(z_start, z_end)
    return total_steps // max(1, int(step_size)) + 1

def focus_stack_preview_lines(z_start: int, z_end: int, step_size: int, maximum: int = 20) -> int:
    return min(int(maximum), focus_stack_frame_count(z_start, z_end, step_size))

def estimate_focus_stack_seconds(
    z_start: int,
    z_end: int,
    step_size: int,
    settle_ms: int,
) -> int:
    frames = focus_stack_frame_count(z_start, z_end, step_size)
    return round(frames * max(0, int(settle_ms)) / 1000)

def tile_count(cols: int, rows: int) -> int:
    return max(0, int(cols)) * max(0, int(rows))

def estimate_tile_scan_seconds(cols: int, rows: int, settle_ms: int) -> int:
    # UI estimate: per-tile settle plus half a second.
    return round(tile_count(cols, rows) * (max(0, int(settle_ms)) / 1000 + 0.5))
