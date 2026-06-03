"""Test the automation plan domain logic."""

from retroscope.domain.automation_plan import (
    estimate_focus_stack_seconds,
    estimate_tile_scan_seconds,
    focus_stack_frame_count,
    focus_stack_preview_lines,
    focus_stack_total_steps,
    tile_count,
)
from retroscope.domain.scan_plan import tile_order


def test_focus_stack_preview_values():
    assert focus_stack_total_steps(100, 160) == 60
    assert focus_stack_total_steps(160, 100) == 60
    assert focus_stack_frame_count(100, 160, 10) == 7
    assert focus_stack_frame_count(100, 160, 0) == 61
    assert focus_stack_preview_lines(0, 1000, 5) == 20
    assert estimate_focus_stack_seconds(100, 160, 10, 150) == 1


def test_tile_scan_preview_values():
    assert tile_count(4, 3) == 12
    assert tile_count(-1, 3) == 0
    assert estimate_tile_scan_seconds(4, 3, 120) == 7


def test_tile_preview_order_shape_matches_scan_plan():
    assert [
        {"col": col, "row": row}
        for col, row in tile_order(3, 2, "serpentine")
    ] == [
        {"col": 0, "row": 0},
        {"col": 1, "row": 0},
        {"col": 2, "row": 0},
        {"col": 2, "row": 1},
        {"col": 1, "row": 1},
        {"col": 0, "row": 1},
    ]
