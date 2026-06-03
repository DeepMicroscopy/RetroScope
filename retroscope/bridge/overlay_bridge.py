"""Overlay bridge: Crosshair & Gird visibility, theme control."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.bridge.config_helpers import ConfigBackedBridgeMixin
from retroscope.services.config_store import ConfigStore


class OverlayBridge(ConfigBackedBridgeMixin, QObject):
    crosshair_changed         = Signal(bool)
    grid_changed              = Signal(bool)
    theme_changed             = Signal(bool)

    def __init__(self, config: ConfigStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._crosshair = True
        self._config.set("ui.crosshair_visible", True)
        self._grid = bool(config.get("ui.grid_visible", False))
        self._dark = bool(config.get("ui.dark_theme", True))

    @Property(bool, notify=crosshair_changed)
    def crosshairVisible(self) -> bool:
        return self._crosshair

    @Slot(bool)
    def setCrosshairVisible(self, v: bool) -> None:
        self._set_setting("_crosshair", "ui.crosshair_visible", v, self.crosshair_changed)

    @Property(bool, notify=grid_changed)
    def gridVisible(self) -> bool:
        return self._grid

    @Slot(bool)
    def setGridVisible(self, v: bool) -> None:
        self._set_setting("_grid", "ui.grid_visible", v, self.grid_changed)

    @Property(bool, notify=theme_changed)
    def darkTheme(self) -> bool:
        return self._dark

    @Slot(bool)
    def setDarkTheme(self, v: bool) -> None:
        self._set_setting("_dark", "ui.dark_theme", v, self.theme_changed)
