"""Sangaboard motor controller driver."""

import logging
import queue
import threading

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from retroscope.drivers import make_driver

logger = logging.getLogger(__name__)

# Hardware constants
SERIAL_PORT = "/dev/ttyAMA0"
BAUD = 115200
POSITION_POLL_INTERVAL_MS = 200  # how often to query board position
QUEUE_GET_TIMEOUT_MS = 50


def _position_poll_empty_ticks() -> int:
    return max(1, int(round(POSITION_POLL_INTERVAL_MS / QUEUE_GET_TIMEOUT_MS)))


# Real driver
class SangaboardDriver(QThread):
    """Sangaboard serial driver thread. Uses pysangaboard's low-level query() for fire-and-forget (lower latency)

    Commands are pushed onto _queue as:
    ("move", dx, dy, dz, protected) fire-and-forget relative move
    ("read_motion_timing", )  read Sangaboard step/ramp timing
    ("set_step_time", us)     set board minimum step delay
    ("set_ramp_time", us)     set board acceleration ramp time
    ("zero", )                set current firmware position to 0,0,0
    ("stop", )                emergency stop
    ("release", )             release motor hold (deenergize)
    ("quit", )                shut down thread
    """

    position_updated = Signal(int, int, int)
    connected_changed = Signal(bool)
    motion_timing_updated = Signal(int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Keep track of pending moves to coalesce
        self._queue: queue.Queue = queue.Queue(maxsize=64)
        self._running = True

    def _drop_pending_moves(self, *, preserve_protected: bool = False) -> int:
        """Remove pending moves. Returns the number of dropped moves."""
        preserved = []
        dropped = 0
        try:
            while True:
                item = self._queue.get_nowait()
                protected_move = item[0] == "move" and len(item) >= 5 and bool(item[4])
                if item[0] != "move" or (preserve_protected and protected_move):
                    preserved.append(item)
                else:
                    dropped += 1
        except queue.Empty:
            pass
        for item in preserved:
            try:
                self._queue.put_nowait(item)
            except queue.Full:
                break
        return dropped

    def move_rel(
        self,
        dx: int,
        dy: int,
        dz: int,
        coalesce: bool = False,
        protected: bool = False,
    ) -> None:
        """Queue a relative move.

        'coalesce=True' Replaces any pending moves with this one, commands don't pile up
        'coalesce=False' Queues every move additively (used for jog buttons and automation)
        'protected=True' Preserves this move from later coalescing.
        """
        if coalesce:
            self._drop_pending_moves(preserve_protected=True)
        try:
            self._queue.put_nowait(("move", dx, dy, dz, bool(protected)))
        except queue.Full:
            pass

    def move_rel_blocking(self, dx: int, dy: int, dz: int, timeout: float | None = None) -> bool:
        """Queue a move and block until the driver thread has completed it.

        e.g. autofocus uses this to make settle delays start after the move is completed.
        """
        done = threading.Event()
        result = {"ok": False}
        try:
            self._queue.put_nowait(("move_blocking", dx, dy, dz, done, result))
        except queue.Full:
            return False
        if not done.wait(timeout):
            return False
        return bool(result["ok"])

    def request_motion_timing(self) -> None:
        try:
            self._queue.put_nowait(("read_motion_timing",))
        except queue.Full:
            pass

    def set_step_time_us(self, value: int) -> None:
        try:
            self._queue.put_nowait(("set_step_time", int(value)))
        except queue.Full:
            pass

    def set_ramp_time_us(self, value: int) -> None:
        try:
            self._queue.put_nowait(("set_ramp_time", int(value)))
        except queue.Full:
            pass

    def zero_position(self) -> None:
        """Queue a firmware position reset to 0,0,0."""
        self._drop_pending_moves()
        try:
            self._queue.put_nowait(("zero",))
        except queue.Full:
            pass

    def stop_motors(self) -> None:
        try:
            self._queue.put_nowait(("stop",))
        except queue.Full:
            pass

    def release_motors(self) -> None:
        self._drop_pending_moves()
        try:
            self._queue.put_nowait(("release",))
        except queue.Full:
            pass

    def request_stop(self) -> None:
        self._running = False
        try:
            self._queue.put_nowait(("quit",))
        except queue.Full:
            pass

    def _read_motion_timing(self, sb) -> tuple[int, int] | None:
        try:
            if hasattr(sb, "flush_input_buffer"):
                sb.flush_input_buffer()
            step_time_us = int(sb.step_time)
            ramp_time_us = int(sb.ramp_time)
            self.motion_timing_updated.emit(step_time_us, ramp_time_us)
            return step_time_us, ramp_time_us
        except Exception:
            return None

    def _set_step_time(self, sb, value: int) -> None:
        try:
            sb.step_time = int(value)
            self._read_motion_timing(sb)
        except Exception:
            pass

    def _set_ramp_time(self, sb, value: int) -> None:
        try:
            sb.ramp_time = int(value)
            self._read_motion_timing(sb)
        except Exception:
            pass

    # Thread body
    def run(self) -> None:
        try:
            from sangaboard import Sangaboard
        except ImportError:
            self.connected_changed.emit(False)
            return

        try:
            with Sangaboard(SERIAL_PORT) as sb:
                self.connected_changed.emit(True)
                pos = list(sb.position)
                self.position_updated.emit(*pos)
                self._read_motion_timing(sb)

                poll_counter = 0
                position_poll_empty_ticks = _position_poll_empty_ticks()
                queue_get_timeout_s = QUEUE_GET_TIMEOUT_MS / 1000.0
                while self._running:
                    try:
                        cmd = self._queue.get(timeout=queue_get_timeout_s)
                    except queue.Empty:
                        # Periodic position refresh
                        poll_counter += 1
                        if poll_counter >= position_poll_empty_ticks:
                            poll_counter = 0
                            try:
                                if hasattr(sb, "flush_input_buffer"):
                                    sb.flush_input_buffer()
                                pos = list(sb.position)
                                self.position_updated.emit(*pos)
                            except Exception:
                                pass
                        continue

                    if cmd[0] == "quit":
                        break
                    elif cmd[0] == "move":
                        _, dx, dy, dz, *_ = cmd
                        try:
                            # Fire-and-forget relative move via raw board query.
                            sb.query(f"mr {int(dx)} {int(dy)} {int(dz)}\n")
                        except Exception:
                            pass
                    elif cmd[0] == "move_blocking":
                        _, dx, dy, dz, done, result = cmd
                        try:
                            if hasattr(sb, "flush_input_buffer"):
                                sb.flush_input_buffer()
                            sb.move_rel([int(dx), int(dy), int(dz)])
                            try:
                                pos = list(sb.position)
                                self.position_updated.emit(*pos)
                            except Exception:
                                pass
                            result["ok"] = True
                        except Exception as e:
                            logger.warning("[sangaboard] blocking move %s failed: %s",
                                           [int(dx), int(dy), int(dz)], e)
                            result["ok"] = False
                        finally:
                            done.set()
                    elif cmd[0] == "read_motion_timing":
                        self._read_motion_timing(sb)
                    elif cmd[0] == "set_step_time":
                        _, value = cmd
                        self._set_step_time(sb, int(value))
                    elif cmd[0] == "set_ramp_time":
                        _, value = cmd
                        self._set_ramp_time(sb, int(value))
                    elif cmd[0] == "zero":
                        try:
                            if hasattr(sb, "zero_position"):
                                sb.zero_position()
                            else:
                                sb.query("zero")
                            try:
                                pos = list(sb.position)
                                self.position_updated.emit(*pos)
                            except Exception:
                                self.position_updated.emit(0, 0, 0)
                        except Exception:
                            pass
                    elif cmd[0] == "stop":
                        try:
                            sb.release_motors()
                        except Exception:
                            pass
                    elif cmd[0] == "release":
                        try:
                            sb.release_motors()
                        except Exception:
                            pass

        except Exception:
            pass
        finally:
            self.connected_changed.emit(False)


# Mock driver
class MockSangaboard(QThread):
    """Simulated Sangaboard for development.

    Uses QTimer to moves toward _target incrementally to simulate realistic motor movement.
    """

    position_updated = Signal(int, int, int)
    connected_changed = Signal(bool)
    motion_timing_updated = Signal(int, int)

    STEP_PER_TICK = 50  # steps moved toward target per timer tick

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pos = [0, 0, 0]
        self._target = [0, 0, 0]
        self._lock = threading.Lock()
        self._timer: QTimer | None = None
        self._step_time_us = 1000
        self._ramp_time_us = 0

    def move_rel(
        self,
        dx: int,
        dy: int,
        dz: int,
        coalesce: bool = False,
        protected: bool = False,
    ) -> None:
        # Mock accumulates targets directly, coalesce flag has no effect here.
        del coalesce, protected
        with self._lock:
            self._target[0] += dx
            self._target[1] += dy
            self._target[2] += dz

    def move_rel_blocking(self, dx: int, dy: int, dz: int, timeout: float | None = None) -> bool:
        del timeout
        with self._lock:
            self._pos[0] += int(dx)
            self._pos[1] += int(dy)
            self._pos[2] += int(dz)
            self._target = list(self._pos)
            pos = tuple(self._pos)
        self.position_updated.emit(*pos)
        return True

    def request_motion_timing(self) -> None:
        self.motion_timing_updated.emit(self._step_time_us, self._ramp_time_us)

    def set_step_time_us(self, value: int) -> None:
        self._step_time_us = int(value)
        self.motion_timing_updated.emit(self._step_time_us, self._ramp_time_us)

    def set_ramp_time_us(self, value: int) -> None:
        self._ramp_time_us = int(value)
        self.motion_timing_updated.emit(self._step_time_us, self._ramp_time_us)

    def zero_position(self) -> None:
        with self._lock:
            self._pos = [0, 0, 0]
            self._target = [0, 0, 0]
            pos = tuple(self._pos)
        self.position_updated.emit(*pos)

    def stop_motors(self) -> None:
        with self._lock:
            self._target = list(self._pos)

    def release_motors(self) -> None:
        with self._lock:
            self._target = list(self._pos)

    def request_stop(self) -> None:
        self.quit()

    def run(self) -> None:
        self.connected_changed.emit(True)
        self.request_motion_timing()
        self._timer = QTimer()
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.exec()
        self._timer.stop()
        self.connected_changed.emit(False)

    def _tick(self) -> None:
        changed = False
        with self._lock:
            for i in range(3):
                diff = self._target[i] - self._pos[i]
                if diff == 0:
                    continue
                step = min(abs(diff), self.STEP_PER_TICK) * (1 if diff > 0 else -1)
                self._pos[i] += step
                changed = True
            pos = tuple(self._pos)
        if changed:
            self.position_updated.emit(*pos)


# Factory
def create_sangaboard_driver(parent: QObject | None = None) -> SangaboardDriver | MockSangaboard:
    return make_driver(
        lambda: SangaboardDriver(parent),
        lambda: MockSangaboard(parent),
    )
