"""Test the worker lifecycle management."""

from retroscope.services.worker_lifecycle import PausableWorkerLifecycle


class SignalSpy:
    def __init__(self):
        self.values = []

    def emit(self, value):
        self.values.append(value)


class WorkerSpy:
    def __init__(self):
        self.started = False
        self.cancelled = False
        self.paused = False
        self.resumed = False

    def start(self):
        self.started = True

    def request_cancel(self):
        self.cancelled = True

    def request_pause(self):
        self.paused = True

    def request_resume(self):
        self.resumed = True


def test_worker_lifecycle_start_pause_resume_cancel_finish():
    busy = SignalSpy()
    paused = SignalSpy()
    worker = WorkerSpy()
    lifecycle = PausableWorkerLifecycle(busy, paused)

    lifecycle.start(worker)
    assert lifecycle.busy is True
    assert worker.started is True
    assert busy.values == [True]

    lifecycle.pause()
    assert lifecycle.paused is True
    assert worker.paused is True
    assert paused.values == [True]

    lifecycle.resume()
    assert lifecycle.paused is False
    assert worker.resumed is True
    assert paused.values == [True, False]

    lifecycle.cancel()
    assert worker.cancelled is True

    lifecycle.finish()
    assert lifecycle.busy is False
    assert lifecycle.worker is None
    assert busy.values == [True, False]
