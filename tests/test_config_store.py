"""Tests for ConfigStore persistence behavior."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.services.config_store import ConfigStore


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


def test_config_store_autosaves_immediately_when_delay_is_zero(tmp_path, monkeypatch) -> None:
    _app()
    import retroscope.services.config_store as config_store

    monkeypatch.setattr(config_store, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "_CONFIG_FILE", tmp_path / "config.json")
    store = ConfigStore(autosave_delay_ms=0)
    store.load()

    store.set("ui.active_objective", "20x")

    assert (tmp_path / "config.json").exists()
    assert '"active_objective": "20x"' in (tmp_path / "config.json").read_text(encoding="utf-8")
