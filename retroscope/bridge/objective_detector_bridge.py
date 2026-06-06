"""ObjectiveDetectorBridge: Exposes objective change detection settings to QML."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.bridge.config_helpers import ConfigBackedBridgeMixin
from retroscope.services.config_store import CONFIG_RESET_KEY
from retroscope.services.objective_detector import ObjectiveDetector


class ObjectiveDetectorBridge(ConfigBackedBridgeMixin, QObject):
    enabled_changed             = Signal(bool)
    dark_threshold_changed      = Signal(float)
    dark_duration_changed       = Signal(int)
    recovery_threshold_changed  = Signal(float)
    autofocus_on_switch_changed = Signal(bool)
    switchDetected              = Signal()

    def __init__(
        self,
        detector: ObjectiveDetector,
        config,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._det    = detector
        self._config = config
        self._autofocus_on_switch = bool(config.get("detection.autofocus_on_switch", True))
        if hasattr(config, "config_changed"):
            config.config_changed.connect(self._on_config_changed)

        # Forward service signal to QML
        detector.switch_detected.connect(self.switchDetected)


    # Enabled
    @Property(bool, notify=enabled_changed)
    def enabled(self) -> bool:
        return self._det.enabled

    @Slot(bool)
    def setEnabled(self, v: bool) -> None:
        if v == self._det.enabled:
            return
        self._det.set_enabled(v)
        self.enabled_changed.emit(v)


    # Dark threshold
    @Property(float, notify=dark_threshold_changed)
    def darkThresholdPct(self) -> float:
        return self._det.dark_threshold_pct

    @Slot(float)
    def setDarkThresholdPct(self, v: float) -> None:
        self._det.set_dark_threshold_pct(v)
        self.dark_threshold_changed.emit(self._det.dark_threshold_pct)


    # Minimum dark duration
    @Property(int, notify=dark_duration_changed)
    def darkDurationMs(self) -> int:
        return self._det.dark_duration_ms

    @Slot(int)
    def setDarkDurationMs(self, v: int) -> None:
        self._det.set_dark_duration_ms(v)
        self.dark_duration_changed.emit(self._det.dark_duration_ms)


    # Recovery threshold
    @Property(float, notify=recovery_threshold_changed)
    def recoveryThresholdPct(self) -> float:
        return self._det.recovery_threshold_pct

    @Slot(float)
    def setRecoveryThresholdPct(self, v: float) -> None:
        self._det.set_recovery_threshold_pct(v)
        self.recovery_threshold_changed.emit(self._det.recovery_threshold_pct)


    # Autofocus after switch
    @Property(bool, notify=autofocus_on_switch_changed)
    def autofocusOnSwitch(self) -> bool:
        return self._autofocus_on_switch

    @Slot(bool)
    def setAutofocusOnSwitch(self, v: bool) -> None:
        self._set_setting(
            "_autofocus_on_switch",
            "detection.autofocus_on_switch",
            v,
            self.autofocus_on_switch_changed,
        )


    # Control
    @Slot()
    def cancel(self) -> None:
        """Dismiss popup and reset state machine."""
        self._det.cancel()

    def suppress_for_camera_change(self, duration_ms: float = 1500.0) -> None:
        self._det.suppress_temporarily(duration_ms)

    def _on_config_changed(self, key: str) -> None:
        if key != CONFIG_RESET_KEY:
            return
        self._autofocus_on_switch = bool(self._config.get("detection.autofocus_on_switch", True))
        self.enabled_changed.emit(self._det.enabled)
        self.dark_threshold_changed.emit(self._det.dark_threshold_pct)
        self.dark_duration_changed.emit(self._det.dark_duration_ms)
        self.recovery_threshold_changed.emit(self._det.recovery_threshold_pct)
        self.autofocus_on_switch_changed.emit(self._autofocus_on_switch)
