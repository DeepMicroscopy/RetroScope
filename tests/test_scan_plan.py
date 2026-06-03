"""Test the scan plan generation functions."""

from __future__ import annotations

from retroscope.domain.scan_plan import (
    raster_order,
    serpentine_order,
    tile_order,
    tile_step,
    video_scan_segments,
)


def _segments_as_tuples(cols: int, rows: int, pattern: str, step_x: int, step_y: int):
    return [
        (segment.dx, segment.dy, segment.tile_equivalent)
        for segment in video_scan_segments(cols, rows, pattern, step_x, step_y)
    ]


def test_serpentine_order_reverses_alternate_rows() -> None:
    assert serpentine_order(3, 2) == [
        (0, 0),
        (1, 0),
        (2, 0),
        (2, 1),
        (1, 1),
        (0, 1),
    ]


def test_raster_order_keeps_each_row_left_to_right() -> None:
    assert raster_order(3, 2) == [
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (1, 1),
        (2, 1),
    ]


def test_tile_order_uses_raster_fallback_for_unknown_pattern() -> None:
    assert tile_order(2, 2, "unknown") == raster_order(2, 2)


def test_tile_step_preserves_existing_openflexure_approximation() -> None:
    step = tile_step(um_per_pixel=1.0, overlap=0.2)

    assert step.x == 1024
    assert step.y == 576


def test_tile_step_uses_axis_specific_stage_scale_when_calibrated() -> None:
    step = tile_step(
        um_per_pixel=0.5,
        overlap=0.2,
        frame_width_px=1000,
        frame_height_px=500,
        stage_um_per_step_x=0.25,
        stage_um_per_step_y=0.5,
    )

    assert step.x == 1600
    assert step.y == 400


def test_tile_step_uses_each_axis_stage_scale_independently() -> None:
    step = tile_step(
        um_per_pixel=0.5,
        overlap=0.2,
        frame_width_px=1000,
        frame_height_px=500,
        stage_um_per_step_x=0.25,
        stage_um_per_step_y=0.0,
    )

    assert step.x == 1600
    assert step.y == 400


def test_tile_step_clamps_to_at_least_one_step() -> None:
    step = tile_step(um_per_pixel=0.0, overlap=1.5)

    assert step.x == 1
    assert step.y == 1


def test_video_scan_segments_serpentine_are_continuous_rows() -> None:
    assert _segments_as_tuples(3, 2, "serpentine", 1024, 576) == [
        (2048, 0, 3),
        (0, 576, 0),
        (-2048, 0, 3),
    ]


def test_video_scan_segments_raster_return_to_row_start() -> None:
    assert _segments_as_tuples(3, 2, "raster", 1024, 576) == [
        (2048, 0, 3),
        (-2048, 576, 0),
        (2048, 0, 3),
    ]


def test_video_scan_segments_single_column_match_legacy_progress() -> None:
    assert _segments_as_tuples(1, 3, "serpentine", 1024, 576) == [
        (0, 0, 1),
        (0, 576, 1),
        (0, 576, 1),
    ]
