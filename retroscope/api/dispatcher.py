"""Qt-thread command dispatch for REST API actions."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, Signal, Slot


class QtCommandDispatcher(QObject):
    """Execute callables on the Qt thread and wait for their result."""

    _call_requested = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._call_requested.connect(
            self._execute,
            Qt.ConnectionType.QueuedConnection,
        )

    def call(self, func: Callable[[], Any], timeout_s: float = 5.0) -> Any:
        if QCoreApplication.instance() is None or QThread.currentThread() == self.thread():
            return func()

        future: Future[Any] = Future()
        self._call_requested.emit((func, future))
        return future.result(timeout=timeout_s)

    @Slot(object)
    def _execute(self, payload: object) -> None:
        func, future = payload
        if future.done():
            return
        try:
            result = func()
        except BaseException as exc:
            future.set_exception(exc)
        else:
            future.set_result(result)
