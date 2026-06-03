"""Helpers for config QObject bridge state."""

from __future__ import annotations


class ConfigBackedBridgeMixin:
    """Shared setter helpers for bridges that persist config values."""

    def _set_setting(self, attr: str, key: str, value, changed_signal) -> None:
        if value == getattr(self, attr):
            return
        setattr(self, attr, value)
        self._config.set(key, value)
        changed_signal.emit(value)
