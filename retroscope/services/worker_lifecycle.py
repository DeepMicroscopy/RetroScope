"""Shared lifecycle helper for Qt worker services."""

from __future__ import annotations


class PausableWorkerLifecycle:
    """Tracks one pause/cancel capable worker and emits service state changes."""

    def __init__(self, busy_changed, paused_changed) -> None:
        self._busy_changed = busy_changed
        self._paused_changed = paused_changed
        self._worker = None
        self._busy = False
        self._paused = False

    @property
    def worker(self):
        return self._worker

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self, worker) -> None:
        self._worker = worker
        self._paused = False
        self._busy = True
        self._busy_changed.emit(True)
        worker.start()

    def cancel(self) -> None:
        if self._worker and self._busy:
            self._worker.request_cancel()

    def pause(self) -> None:
        if self._worker and self._busy and not self._paused:
            self._worker.request_pause()
            self._paused = True
            self._paused_changed.emit(True)

    def resume(self) -> None:
        if self._worker and self._busy and self._paused:
            self._worker.request_resume()
            self._paused = False
            self._paused_changed.emit(False)

    def finish(self) -> None:
        self._busy = False
        self._paused = False
        self._busy_changed.emit(False)
        self._worker = None
