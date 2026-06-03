"""Test the polling logic for the SangaBoard driver."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import retroscope.drivers.sangaboard as sangaboard


def test_position_poll_ticks_are_derived_from_interval(monkeypatch) -> None:
    monkeypatch.setattr(sangaboard, "POSITION_POLL_INTERVAL_MS", 250)
    monkeypatch.setattr(sangaboard, "QUEUE_GET_TIMEOUT_MS", 50)

    assert sangaboard._position_poll_empty_ticks() == 5


def test_position_poll_ticks_are_at_least_one(monkeypatch) -> None:
    monkeypatch.setattr(sangaboard, "POSITION_POLL_INTERVAL_MS", 10)
    monkeypatch.setattr(sangaboard, "QUEUE_GET_TIMEOUT_MS", 50)

    assert sangaboard._position_poll_empty_ticks() == 1
