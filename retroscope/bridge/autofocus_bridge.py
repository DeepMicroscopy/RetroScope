"""AutofocusBridge: Exposes AutofocusService state to QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.autofocus import AutofocusService


class AutofocusBridge(QObject):
    busy_changed       = Signal(bool)
    cancelling_changed = Signal(bool)
    progress_changed   = Signal(float)
    autofocus_failed   = Signal(str)   # reason, fires on cancel or low confidence

    def __init__(self, service: AutofocusService,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._svc = service
        self._progress: float = 0.0

        service.busy_changed.connect(self.busy_changed)
        service.cancelling_changed.connect(self.cancelling_changed)
        service.progress.connect(self._on_progress)
        service.finished.connect(self._on_finished)
        service.failed.connect(self.autofocus_failed)

    def _on_progress(self, v: float) -> None:
        self._progress = v
        self.progress_changed.emit(v)

    def _on_finished(self) -> None:
        self._progress = 0.0
        self.progress_changed.emit(0.0)

    @Property(bool, notify=busy_changed)
    def busy(self) -> bool:
        return self._svc.busy

    @Property(bool, notify=cancelling_changed)
    def cancelling(self) -> bool:
        return self._svc.cancelling

    @Property(float, notify=progress_changed)
    def progress(self) -> float:
        return self._progress

    @Slot()
    def startAutofocus(self) -> None:
        self._svc.start_autofocus()

    @Slot()
    def cancelAutofocus(self) -> None:
        self._svc.cancel()

    @Slot()
    def toggleAutofocus(self) -> None:
        """Start AF or cancel it if already running (toggle)."""
        self._svc.toggle()
