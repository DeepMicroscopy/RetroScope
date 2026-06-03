"""Helpers for config QObject bridge state."""

from __future__ import annotations


class ConfigBackedBridgeMixin:
    """Shared setter helpers for bridges that persist config values."""

    def _set_allowed_setting(
        self,
        attr: str,
        key: str,
        value,
        allowed,
        changed_signal,
    ) -> None:
        if value in allowed:
            self._set_setting(attr, key, value, changed_signal)

    def _set_setting(self, attr: str, key: str, value, changed_signal) -> None:
        if value == getattr(self, attr):
            return
        setattr(self, attr, value)
        self._config.set(key, value)
        changed_signal.emit(value)

    def _set_state_setting(self, state, attr: str, key: str, value, changed_signal) -> None:
        if value == getattr(state, attr):
            return
        setattr(state, attr, value)
        self._config.set(key, value)
        changed_signal.emit(value)

    def _set_allowed_state_setting(
        self,
        state,
        attr: str,
        key: str,
        value,
        allowed,
        changed_signal,
    ) -> None:
        if value in allowed:
            self._set_state_setting(state, attr, key, value, changed_signal)

    @staticmethod
    def _clamped_int(value, lower: int, upper: int) -> int:
        return max(lower, min(upper, int(value)))

    @staticmethod
    def _clamped_float(value, lower: float, upper: float, ndigits: int | None = None) -> float:
        clamped = max(lower, min(upper, float(value)))
        return round(clamped, ndigits) if ndigits is not None else clamped
