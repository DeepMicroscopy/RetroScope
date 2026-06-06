"""Tests for SangaBoard driver queueing, polling, and mock behavior."""

from __future__ import annotations

import queue

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

import retroscope.drivers.sangaboard as sangaboard
from retroscope.drivers.sangaboard import MockSangaboard, SangaboardDriver


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def test_position_poll_ticks_are_derived_from_interval(monkeypatch) -> None:
    monkeypatch.setattr(sangaboard, "POSITION_POLL_INTERVAL_MS", 250)
    monkeypatch.setattr(sangaboard, "QUEUE_GET_TIMEOUT_MS", 50)

    assert sangaboard._position_poll_empty_ticks() == 5


def test_position_poll_ticks_are_at_least_one(monkeypatch) -> None:
    monkeypatch.setattr(sangaboard, "POSITION_POLL_INTERVAL_MS", 10)
    monkeypatch.setattr(sangaboard, "QUEUE_GET_TIMEOUT_MS", 50)

    assert sangaboard._position_poll_empty_ticks() == 1


def test_sangaboard_coalesce_preserves_non_move_commands_and_drops_pending_moves() -> None:
    driver = SangaboardDriver()
    driver._queue.put_nowait(("zero",))
    driver.move_rel(1, 0, 0, coalesce=False)
    driver.move_rel(2, 0, 0, coalesce=False)
    driver.move_rel(9, 0, 0, coalesce=True)

    queued = []
    try:
        while True:
            queued.append(driver._queue.get_nowait())
    except queue.Empty:
        pass

    assert queued == [("zero",), ("move", 9, 0, 0)]


def test_sangaboard_timing_commands_are_queued() -> None:
    driver = SangaboardDriver()

    driver.request_motion_timing()
    driver.set_step_time_us(750)
    driver.set_ramp_time_us(25000)

    queued = [driver._queue.get_nowait() for _ in range(3)]
    assert queued == [
        ("read_motion_timing",),
        ("set_step_time", 750),
        ("set_ramp_time", 25000),
    ]


def test_mock_sangaboard_zero_position_resets_position() -> None:
    _app()
    mock = MockSangaboard()
    mock.move_rel(10, 20, 30)
    mock._pos = [7, 8, 9]
    mock._target = [10, 20, 30]

    mock.zero_position()

    assert mock._pos == [0, 0, 0]
    assert mock._target == [0, 0, 0]


def test_mock_sangaboard_reports_board_timing() -> None:
    _app()
    mock = MockSangaboard()
    seen: list[tuple[int, int]] = []
    mock.motion_timing_updated.connect(lambda step, ramp: seen.append((step, ramp)))

    mock.request_motion_timing()
    mock.set_step_time_us(800)
    mock.set_ramp_time_us(20000)

    assert seen == [(1000, 0), (800, 0), (800, 20000)]
