"""Objective change detector: Qt adapter around 'domain.objective_detection'."""

import threading
import time

from PySide6.QtCore import QObject, Signal

from retroscope.domain.objective_detection import DetectorState, Event, Phase, step
from retroscope.services.config_store import ConfigStore


class ObjectiveDetector(QObject):
    """Monitors mean frame brightness and signals when a turret rotation (darkness -> recovery cycle) is detected."""

    switch_detected = Signal()

    def __init__(self, config: ConfigStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._lock   = threading.Lock()

        self._enabled                = bool(config.get("detection.enabled", True))
        self._dark_threshold_pct     = float(config.get("detection.dark_threshold_pct", 15.0))
        self._dark_duration_ms       = int(config.get("detection.dark_duration_ms", 200))
        self._recovery_threshold_pct = float(config.get("detection.recovery_threshold_pct", 40.0))

        self._state = DetectorState()

    # Called from camera analysis thread (direct connection)
    def on_brightness_updated(self, brightness: float) -> None:
        with self._lock:
            if not self._enabled:
                return
            event = step(
                self._state,
                brightness,
                now_ms=time.monotonic() * 1000.0,
                dark_threshold_pct=self._dark_threshold_pct,
                dark_duration_ms=self._dark_duration_ms,
                recovery_threshold_pct=self._recovery_threshold_pct,
            )
        if event is Event.SWITCH:
            self.switch_detected.emit()

    # Control
    def cancel(self) -> None:
        """Reset state machine without emitting switch_detected."""
        with self._lock:
            self._state = DetectorState()

    # Config setters
    def set_enabled(self, v: bool) -> None:
        with self._lock:
            self._enabled = v
            self._config.set("detection.enabled", v)
            if not v:
                self._state.phase = Phase.NORMAL

    def set_dark_threshold_pct(self, v: float) -> None:
        with self._lock:
            self._dark_threshold_pct = max(1.0, min(50.0, v))
            self._config.set("detection.dark_threshold_pct", self._dark_threshold_pct)

    def set_dark_duration_ms(self, v: int) -> None:
        with self._lock:
            self._dark_duration_ms = max(50, min(1000, v))
            self._config.set("detection.dark_duration_ms", self._dark_duration_ms)

    def set_recovery_threshold_pct(self, v: float) -> None:
        with self._lock:
            self._recovery_threshold_pct = max(10.0, min(80.0, v))
            self._config.set("detection.recovery_threshold_pct", self._recovery_threshold_pct)

    # Read-only properties
    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def dark_threshold_pct(self) -> float:
        return self._dark_threshold_pct

    @property
    def dark_duration_ms(self) -> int:
        return self._dark_duration_ms

    @property
    def recovery_threshold_pct(self) -> float:
        return self._recovery_threshold_pct
