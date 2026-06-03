"""Update bridge: OTA update state for QML SettingsView."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.update_service import UpdateService


class UpdateBridge(QObject):
    state_changed = Signal()
    version_changed = Signal(str)

    def __init__(self, service: UpdateService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._svc = service
        self._available = False
        self._checking = False
        self._applying = False
        self._status = ""
        self._version = service.get_version()

        service.update_found.connect(self._on_update_found)
        service.update_complete.connect(self._on_update_complete)
        service.update_failed.connect(self._on_update_failed)
        service.progress.connect(self._on_progress)

    @Property(str, notify=version_changed)
    def currentVersion(self) -> str:
        return self._version

    @Property(bool, notify=state_changed)
    def updateAvailable(self) -> bool:
        return self._available

    @Property(bool, notify=state_changed)
    def checking(self) -> bool:
        return self._checking

    @Property(bool, notify=state_changed)
    def applying(self) -> bool:
        return self._applying

    @Property(str, notify=state_changed)
    def statusMessage(self) -> str:
        return self._status

    @Slot()
    def checkForUpdates(self) -> None:
        self._checking = True
        self._status = "Checking..."
        self.state_changed.emit()
        self._svc.check_for_updates()

    @Slot()
    def applyUpdate(self) -> None:
        self._applying = True
        self._status = "Applying update..."
        self.state_changed.emit()
        self._svc.apply_update()

    def _on_update_found(self, available: bool, message: str) -> None:
        self._checking = False
        self._available = available
        self._status = message
        self.state_changed.emit()

    def _on_update_complete(self) -> None:
        self._applying = False
        self._status = "Update applied. Restarting..." if self._svc.last_restart_requested else "Update applied. Restart required"
        self.state_changed.emit()

    def _on_update_failed(self, error: str) -> None:
        self._applying = False
        self._status = f"Update failed: {error}"
        self.state_changed.emit()

    def _on_progress(self, msg: str) -> None:
        self._status = msg
        self.state_changed.emit()
