"""Status bridge: Sangaboard connection and endstop state for QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot


class StatusBridge(QObject):
    connection_changed = Signal(bool)
    endstop_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._connected = False
        self._endstop = False

    @Property(bool, notify=connection_changed)
    def sangaboardConnected(self) -> bool:
        return self._connected

    @Slot(bool)
    def on_connection_changed(self, connected: bool) -> None:
        self._connected = connected
        self.connection_changed.emit(connected)

    @Property(bool, notify=endstop_changed)
    def endstopTriggered(self) -> bool:
        return self._endstop

    @Slot(bool)
    def on_endstop_changed(self, triggered: bool) -> None:
        self._endstop = triggered
        self.endstop_changed.emit(triggered)
