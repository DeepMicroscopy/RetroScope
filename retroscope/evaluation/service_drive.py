"""Drive the async Qt services (autofocus / focus-stacker / tile-scanner) from the
evaluation worker thread and wait for completion.

Note: Partially AI-generated.
"""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QObject, Qt, QTimer, Signal, Slot


class MainThreadInvoker(QObject):
    """Runs a callable on the thread this object lives in (the main thread)."""

    _trigger = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._trigger.connect(self._run)

    @Slot(object)
    def _run(self, fn) -> None:
        try:
            fn()
        except Exception as e:
            print(f"[eval] main-thread call failed: {e}")

    def call(self, fn) -> None:
        self._trigger.emit(fn)


class _Waiter(QObject):
    """Worker-thread receiver that records the first terminal signal and quits a loop."""

    def __init__(self, loop: QEventLoop) -> None:
        super().__init__()
        self._loop = loop
        self.status: str | None = None
        self.payload = None

    def _finish(self, status: str, args) -> None:
        if self.status is None:
            self.status = status
            self.payload = args[0] if args else None
        self._loop.quit()

    @Slot()
    @Slot(str)
    @Slot(int)
    @Slot(float)
    def on_success(self, *args) -> None:
        self._finish("success", args)

    @Slot()
    @Slot(str)
    def on_failure(self, *args) -> None:
        self._finish("failure", args)


def run_async(
    invoker: MainThreadInvoker,
    start_fn,
    success_signals: list,
    failure_signals: list | None = None,
    timeout_s: float = 180.0,
) -> tuple[str, object]:
    loop = QEventLoop()
    waiter = _Waiter(loop)
    for sig in success_signals:
        sig.connect(waiter.on_success, Qt.ConnectionType.QueuedConnection)
    for sig in (failure_signals or []):
        sig.connect(waiter.on_failure, Qt.ConnectionType.QueuedConnection)

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout_s * 1000))

    invoker.call(start_fn)
    loop.exec()
    timer.stop()

    for sig in success_signals:
        try:
            sig.disconnect(waiter.on_success)
        except (RuntimeError, TypeError):
            pass
    for sig in (failure_signals or []):
        try:
            sig.disconnect(waiter.on_failure)
        except (RuntimeError, TypeError):
            pass

    if waiter.status is None:
        return ("timeout", None)
    return (waiter.status, waiter.payload)
