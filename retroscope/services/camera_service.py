"""Camera service: Stores latest frame and handles snapshot capture.

Note: Partially AI-generated
"""

import logging
import time
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import QMetaObject, QObject, Qt, Signal, Slot

from retroscope.domain.focus_metrics import laplacian_variance
from retroscope.services import ome_tiff
from retroscope.services.config_store import ConfigStore

_DEFAULT_CAPTURE_ROOT = Path.home() / "retroscope" / "captures"
_HIST_BINS = 64                     # number of histogram buckets
_HIST_INTERVAL = 0.25               # seconds between histogram/focus updates
_METRIC_SMOOTHING = 0.35
_HIST_SMOOTHING = 0.18
_HIST_SCALE_SMOOTHING = 0.08
_FPS_WINDOW = 30                    # rolling window size for FPS calculation
_FPS_EMIT_INTERVAL = 1.0            # seconds between fps_updated emits
_UI_FRAME_INTERVAL = 1.0 / 30.0
_FOCUS_ROI = 0.33                   # use centre third of frame for Laplacian
_SOURCE_FOCUS_STALE_S = 1.0
_SOURCE_FOCUS_SPIKE_RATIO = 2.5
_SOURCE_FOCUS_SPIKE_FLOOR = 500.0
_RECORDING_QUEUE_FRAMES = 8
logger = logging.getLogger(__name__)


class _AsyncVideoRecorder:
    """Small frame queue around cv2.VideoWriter so capture callbacks never block."""

    def __init__(self, writer) -> None:
        self._writer = writer
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=_RECORDING_QUEUE_FRAMES)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def enqueue(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame.copy())
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame.copy())
            except queue.Full:
                pass

    def close(self) -> None:
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(None)
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while True:
            frame = self._queue.get()
            if frame is None:
                break
            try:
                self._writer.write(frame[:, :, ::-1])
            except Exception:
                pass
        try:
            self._writer.release()
        except Exception:
            pass


class CameraService(QObject):
    """Receives frames from the camera driver and manages snapshot saves."""

    frame_available       = Signal()           # new frame ready for image provider
    snapshot_saved        = Signal(str)        # path of saved snapshot
    snapshot_failed       = Signal(str)        # reason of failed snapshot
    capture_busy_changed  = Signal(bool)       # native capture in progress
    histogram_updated     = Signal(list)       # 64 ints [0..100], luminance histogram
    focus_score_updated   = Signal(float)      # raw Laplacian variance
    focus_source_updated  = Signal(str)        # "source" or "analysis"
    brightness_updated    = Signal(float)      # mean luminance 0–255, for objective detection
    recording_changed     = Signal(bool)       # recording started/stopped
    recording_saved       = Signal(str)
    fps_updated           = Signal(float)

    def __init__(
        self,
        config: ConfigStore,
        image_store=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._image_store = image_store
        self._lock = threading.Lock()
        self._frame_cond = threading.Condition(self._lock)
        self._latest_frame: np.ndarray | None = None
        self._frame_seq = 0
        self._raw_focus_seq = 0
        self._latest_raw_focus_score: float | None = None
        self._latest_raw_focus_t: float = 0.0
        self._latest_raw_focus_source: str = ""
        self._source_focus_seq = 0
        self._latest_source_focus_score: float | None = None
        self._latest_source_focus_t: float = 0.0
        self._stable_source_focus_score: float | None = None
        self._pending_source_focus_score: float | None = None
        self._focus_source: str = ""
        self._recording_backend = None
        self._native_capture_backend = None
        self._native_recording = False
        self._shutdown_event = threading.Event()

        # Recording state
        self._recording = False
        self._writer = None   # cv2.VideoWriter when active
        self._recorder: _AsyncVideoRecorder | None = None
        self._recording_path: Path | None = None
        self._recording_started_at: datetime | None = None
        self._recording_started_monotonic: float = 0.0
        self._recording_objective: str = ""
        self._recording_position: dict[str, int | None] = {"x": 0, "y": 0, "z": 0}
        self._recording_dims: tuple[int, int] = (0, 0)

        # Last focus score and display smoothing. AF samples bypass the smoothing.
        self._last_focus_score: float = 0.0
        self._hist_ema: np.ndarray | None = None
        self._hist_scale_ema: float | None = None
        self._focus_score_ema: float | None = None

        # FPS measurement
        self._fps_times: list[float] = []
        self._fps_last_emit: float = 0.0
        self._ui_frame_pending = False
        self._ui_last_emit: float = 0.0

        # Capture metadata providers
        self._get_position: Callable[[], tuple[int, int, int]] = lambda: (0, 0, 0)
        self._get_objective: Callable[[], str] = lambda: ""

        # Histogram + fallback focus-score background thread.
        self._analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self._analysis_thread.start()

    def shutdown(self) -> None:
        """Stop background work before Qt receivers start being destroyed."""
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()
        if self.is_recording():
            self.stop_recording()
        self._analysis_thread.join(timeout=1.0)

    def set_metadata_provider(
        self,
        get_position: Callable[[], tuple[int, int, int]],
        get_objective: Callable[[], str],
    ) -> None:
        """Set runtime metadata providers for new captures."""
        self._get_position = get_position
        self._get_objective = get_objective

    def set_recording_backend(self, backend) -> None:
        self._recording_backend = backend

    def set_native_capture_backend(self, backend) -> None:
        self._native_capture_backend = backend

    def capture_native_frame(
        self,
        timeout_s: float = 3.0,
        should_cancel=None,
        allow_tap_fallback: bool = True,
    ) -> np.ndarray | None:
        """Returns a fresh native-resolution frame, optionally falling back to the latest tap frame for single captures while allowing multi-frame workflows to avoid mixed frame sizes."""

        backend = self._native_capture_backend
        if backend is not None and hasattr(backend, "capture_native_to_array_sync"):
            try:
                arr = backend.capture_native_to_array_sync(timeout_s, should_cancel)
            except TypeError:
                arr = backend.capture_native_to_array_sync(timeout_s)
            except Exception as e:
                print(f"[capture] native backend failed: {e}")
                arr = None
            if arr is not None:
                return arr
            if not allow_tap_fallback:
                return None
            print(
                "[capture] native backend returned no frame, falling back to the analysis-resolution tap frame"
            )
        if not allow_tap_fallback:
            return None
        with self._lock:
            frame = self._latest_frame
        return frame.copy() if frame is not None else None

    def native_capture_frame_size(self) -> tuple[int, int]:
        """Return the expected native still-capture frame size, if known."""
        backend = self._native_capture_backend
        if backend is not None:
            for method_name in ("native_capture_size", "recording_dimensions"):
                method = getattr(backend, method_name, None)
                if method is None:
                    continue
                try:
                    width, height = method()
                except Exception:
                    continue
                width = int(width)
                height = int(height)
                if width > 0 and height > 0:
                    return width, height
        with self._lock:
            frame = self._latest_frame
        if frame is not None:
            h, w = frame.shape[:2]
            if w > 0 and h > 0:
                return int(w), int(h)
        return 0, 0

    # Frame analysis (histogram + focus quality)
    def _compute_histogram(self, frame: np.ndarray) -> list[float]:
        """Return luminance histogram counts with light neighbor-bin smoothing."""
        lum = (
            0.299 * frame[:, :, 0].astype(np.float32)
            + 0.587 * frame[:, :, 1].astype(np.float32)
            + 0.114 * frame[:, :, 2].astype(np.float32)
        ).astype(np.uint8)
        counts, _ = np.histogram(lum, bins=_HIST_BINS, range=(0, 256))
        counts_f = counts.astype(np.float32)
        if counts_f.sum() <= 0:
            return [0.0] * _HIST_BINS
        padded = np.pad(counts_f, (1, 1), mode="edge")
        smoothed = (
            padded[:-2] * 0.25
            + padded[1:-1] * 0.5
            + padded[2:] * 0.25
        )
        return smoothed.tolist()

    def _compute_focus_score(self, frame: np.ndarray) -> float:
        """Return raw Laplacian variance over the centre ROI."""
        return laplacian_variance(frame, roi=_FOCUS_ROI)

    def _store_raw_focus_score_locked(self, score: float, source: str, now: float) -> float:
        raw_score = max(0.0, float(score))
        self._latest_raw_focus_score = raw_score
        self._latest_raw_focus_t = now
        self._latest_raw_focus_source = source
        self._raw_focus_seq += 1
        self._frame_cond.notify_all()
        return raw_score

    @Slot()
    def reset_focus_reference(self) -> None:
        self._focus_score_ema = None
        with self._frame_cond:
            self._stable_source_focus_score = None
            self._pending_source_focus_score = None

    def _stable_focus_score(self, score: float) -> float:
        """Reject focus spikes while staying realtime."""
        value = max(0.0, float(score))
        stable = self._stable_source_focus_score
        if stable is None:
            self._stable_source_focus_score = value
            self._pending_source_focus_score = None
            return value

        spike_threshold = max(_SOURCE_FOCUS_SPIKE_FLOOR, stable * _SOURCE_FOCUS_SPIKE_RATIO)
        if value > spike_threshold:
            pending = self._pending_source_focus_score
            self._pending_source_focus_score = value
            if pending is None:
                return stable
            similar_to_pending = (
                min(value, pending) / max(value, pending, 1.0) >= 0.5
                or abs(value - pending) < _SOURCE_FOCUS_SPIKE_FLOOR
            )
            if not similar_to_pending:
                return stable

        self._stable_source_focus_score = value
        self._pending_source_focus_score = None
        return value

    def on_focus_score_ready(self, score: float) -> None:
        """Receive a focus score computed from the native camera source frame."""
        now = time.monotonic()
        with self._frame_cond:
            raw_score = self._store_raw_focus_score_locked(score, "source", now)
            clean_score = self._stable_focus_score(raw_score)
            self._latest_source_focus_score = clean_score
            self._latest_source_focus_t = now
            self._last_focus_score = clean_score
            self._focus_source = "source"
            self._source_focus_seq += 1
            self._frame_cond.notify_all()
        self.focus_score_updated.emit(self._smooth_focus_score(clean_score))
        self.focus_source_updated.emit("source")

    def source_focus_available(self) -> bool:
        with self._lock:
            return (
                self._latest_source_focus_score is not None
                and time.monotonic() - self._latest_source_focus_t <= _SOURCE_FOCUS_STALE_S
            )

    def focus_sequence(self) -> int:
        with self._lock:
            return self._source_focus_seq

    def raw_focus_sequence(self) -> int:
        with self._lock:
            return self._raw_focus_seq

    def raw_focus_status(self) -> tuple[int, float | None, float | None, str]:
        """Return sequence, latest raw score, age in seconds and source label."""
        with self._lock:
            age = (
                time.monotonic() - self._latest_raw_focus_t
                if self._latest_raw_focus_score is not None
                else None
            )
            return (
                self._raw_focus_seq,
                self._latest_raw_focus_score,
                age,
                self._latest_raw_focus_source,
            )

    def wait_for_next_raw_focus_score(
        self,
        after_sequence: int | None = None,
        timeout: float = 0.5,
    ) -> float | None:
        """Wait for an unsmoothed, unstabilized focus score."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._frame_cond:
            target = self._raw_focus_seq if after_sequence is None else int(after_sequence)
            while self._raw_focus_seq <= target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._frame_cond.wait(remaining)
            if self._raw_focus_seq <= target:
                return None
            return self._latest_raw_focus_score

    def wait_for_next_focus_score(
        self,
        after_sequence: int | None = None,
        timeout: float = 0.5,
    ) -> float | None:
        """Wait for a source-resolution focus score."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._frame_cond:
            target = self._source_focus_seq if after_sequence is None else int(after_sequence)
            while self._source_focus_seq <= target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._frame_cond.wait(remaining)
            if self._source_focus_seq <= target:
                return None
            return self._latest_source_focus_score

    def _analysis_loop(self) -> None:
        """Background loop: emit histogram and fallback focus scores."""
        while not self._shutdown_event.wait(_HIST_INTERVAL):
            with self._lock:
                frame = self._latest_frame
                source_focus_fresh = (
                    self._latest_source_focus_score is not None
                    and time.monotonic() - self._latest_source_focus_t <= _SOURCE_FOCUS_STALE_S
                )
            if frame is None:
                continue
            try:
                hist = self._smooth_histogram(self._compute_histogram(frame))
                self.histogram_updated.emit(hist)
                if not source_focus_fresh:
                    raw_focus = self._compute_focus_score(frame)
                    with self._frame_cond:
                        self._store_raw_focus_score_locked(raw_focus, "analysis", time.monotonic())
                        self._last_focus_score = raw_focus
                    if self._focus_source != "analysis":
                        self._focus_source = "analysis"
                        self.focus_source_updated.emit("analysis")
                    self.focus_score_updated.emit(self._smooth_focus_score(self._last_focus_score))
                # "Objective-change brightness" is fed per-frame from on_frame_ready fast, for quick turret flick
            except RuntimeError as e:
                if self._shutdown_event.is_set() or "deleted" in str(e).lower():
                    return
                logger.warning("[analysis] error: %s", e)
            except Exception as e:
                if self._shutdown_event.is_set():
                    return
                logger.warning("[analysis] error: %s", e)

    def _smooth_histogram(self, hist: list[float]) -> list[int]:
        values = np.asarray(hist, dtype=np.float32)
        total = float(values.sum())
        if total <= 0:
            return [0] * _HIST_BINS
        values = values / total
        if self._hist_ema is None or self._hist_ema.shape != values.shape:
            self._hist_ema = values
            self._hist_scale_ema = max(float(values.max()), 1e-6)
        else:
            a = _HIST_SMOOTHING
            self._hist_ema = a * values + (1.0 - a) * self._hist_ema
            peak = max(float(self._hist_ema.max()), 1e-6)
            if self._hist_scale_ema is None:
                self._hist_scale_ema = peak
            else:
                s = _HIST_SCALE_SMOOTHING
                self._hist_scale_ema = s * peak + (1.0 - s) * self._hist_scale_ema
        scale = max(float(self._hist_scale_ema or 0.0), 1e-6)
        bars = self._hist_ema / scale * 100.0
        return [int(round(v)) for v in np.clip(bars, 0, 100)]

    def _smooth_focus_score(self, value: float) -> float:
        v = max(0.0, float(value))
        if self._focus_score_ema is None:
            self._focus_score_ema = v
        else:
            a = _METRIC_SMOOTHING
            self._focus_score_ema = a * v + (1.0 - a) * self._focus_score_ema
        return float(self._focus_score_ema)

    # Recording
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start_recording(self) -> None:
        """Start recording frames to a timestamped video file."""
        try:
            import cv2
        except ImportError:
            cv2 = None
        with self._lock:
            if self._recording:
                return
            frame = self._latest_frame
        backend = self._recording_backend
        backend_dims = (0, 0)
        if backend is not None and hasattr(backend, "recording_dimensions"):
            try:
                backend_dims = backend.recording_dimensions()
            except Exception:
                backend_dims = (0, 0)
        if frame is None and backend_dims == (0, 0):
            print("[recording] no frame available yet")
            return

        if backend_dims != (0, 0):
            w, h = backend_dims
        else:
            h, w = frame.shape[:2]
        objective = self._safe_objective()
        position = self._safe_position()
        native_path = self._recording_path_for("video", objective, ".mp4", datetime.now().strftime("%Y%m%d_%H%M%S"))
        if backend is not None and hasattr(backend, "start_recording_to"):
            try:
                if backend.start_recording_to(str(native_path)):
                    with self._lock:
                        if self._recording:
                            backend.stop_recording()
                            return
                        self._native_recording = True
                        self._recording = True
                        self._recording_path = native_path
                        self._recording_started_at = datetime.now()
                        self._recording_started_monotonic = time.monotonic()
                        self._recording_objective = objective
                        self._recording_position = position
                        self._recording_dims = (int(w), int(h))
                    self.recording_changed.emit(True)
                    print(f"[recording] started (Qt native) -> {native_path}")
                    return
            except Exception as e:
                print(f"[recording] native recorder unavailable: {e}")

        if cv2 is None:
            print("[recording] cv2 not available")
            return
        writer, path, codec = self._open_recording_writer(cv2, w, h, objective)
        if writer is None or path is None:
            print("[recording] failed to open writer")
            return

        with self._lock:
            if self._recording:
                writer.release()
                return
            self._writer = writer
            self._recorder = _AsyncVideoRecorder(writer)
            self._recording = True
            self._recording_path = path
            self._recording_started_at = datetime.now()
            self._recording_started_monotonic = time.monotonic()
            self._recording_objective = objective
            self._recording_position = position
            self._recording_dims = (w, h)
        self.recording_changed.emit(True)
        print(f"[recording] started ({codec}) -> {path}")

    def stop_recording(self) -> None:
        """Stop and finalise the current recording."""
        with self._lock:
            was_recording = self._recording or self._writer is not None
            writer = self._writer
            recorder = self._recorder
            path = self._recording_path
            captured_at = self._recording_started_at
            started_monotonic = self._recording_started_monotonic
            dims = self._recording_dims
            objective = self._recording_objective
            position = dict(self._recording_position)

            self._recording = False
            self._native_recording = False
            self._writer = None
            self._recorder = None
            self._recording_path = None
            self._recording_started_at = None
            self._recording_started_monotonic = 0.0
            self._recording_objective = ""
            self._recording_position = {"x": 0, "y": 0, "z": 0}
            self._recording_dims = (0, 0)

        if not was_recording:
            return

        if recorder is not None:
            recorder.close()
        elif writer is None and self._recording_backend is not None:
            try:
                self._recording_backend.stop_recording()
            except Exception as e:
                print(f"[recording] native recorder stop failed: {e}")
        elif writer is not None:
            try:
                writer.release()
            except Exception as e:
                print(f"[recording] release failed: {e}")
        self.recording_changed.emit(False)
        if path is not None:
            self._write_video_metadata(
                path,
                captured_at=captured_at,
                started_monotonic=started_monotonic,
                dims=dims,
                objective=objective,
                position=position,
            )
            self.recording_saved.emit(str(path))
        print("[recording] stopped")

    def _open_recording_writer(
        self,
        cv2,
        width: int,
        height: int,
        objective: str,
    ):
        """Try preferred output formats/codecs in order and return first working writer."""
        rec_dir = self._recording_dir()
        rec_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidates = [
            ("MP4V", self._recording_path_for("video", objective, ".mp4", timestamp), "mp4v"),
            ("XVID", self._recording_path_for("video", objective, ".avi", timestamp), "XVID"),
            ("MJPG", self._recording_path_for("video", objective, ".avi", timestamp), "MJPG"),
        ]
        for label, path, fourcc_text in candidates:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_text)
            writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, height))
            if writer.isOpened():
                return writer, path, label
            writer.release()
            try:
                if path.exists() and path.stat().st_size == 0:
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        return None, None, ""

    def _recording_path_for(self, media_type: str, objective: str, extension: str, timestamp: str) -> Path:
        if self._image_store is not None:
            return self._image_store.new_image_path("video", media_type, objective=objective, extension=extension)
        return self._recording_dir() / f"microscope_{timestamp}{extension}"

    # Frame delivery
    def get_latest_frame(self) -> np.ndarray | None:
        """Thread-safe frame access (used by autofocus worker and image provider)."""
        with self._lock:
            return self._latest_frame

    def frame_sequence(self) -> int:
        with self._lock:
            return self._frame_seq

    def wait_for_next_frame(
        self,
        after_sequence: int | None = None,
        timeout: float = 0.5,
    ) -> np.ndarray | None:
        """Wait for a frame and return a copy."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._frame_cond:
            target = self._frame_seq if after_sequence is None else int(after_sequence)
            while self._frame_seq <= target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._frame_cond.wait(remaining)
            frame = self._latest_frame
            return frame.copy() if frame is not None else None

    @Slot(object)
    def on_frame_ready(self, frame: object) -> None:
        now = time.monotonic()
        should_schedule_ui = False
        focus_score: float | None = None
        brightness: float | None = None
        if isinstance(frame, np.ndarray):
            focus_score = self._compute_focus_score(frame)
        if isinstance(frame, np.ndarray) and frame.ndim >= 2:
            # Uses a cheap strided brightness sample so the objective detector can catch brief turret-rotation dark frames.
            brightness = float(frame[::8, ::8].mean())
        with self._frame_cond:
            self._latest_frame = frame
            self._frame_seq += 1
            self._frame_cond.notify_all()
            recorder = self._recorder if self._recording else None
            self._fps_times.append(now)
            if len(self._fps_times) > _FPS_WINDOW:
                self._fps_times.pop(0)
            if now - self._fps_last_emit >= _FPS_EMIT_INTERVAL and len(self._fps_times) >= 2:
                span = self._fps_times[-1] - self._fps_times[0]
                fps = (len(self._fps_times) - 1) / span if span > 0 else 0.0
                self._fps_last_emit = now
                self.fps_updated.emit(fps)
            if (
                not self._ui_frame_pending
                and now - self._ui_last_emit >= _UI_FRAME_INTERVAL
            ):
                self._ui_frame_pending = True
                should_schedule_ui = True
        if should_schedule_ui:
            QMetaObject.invokeMethod(
                self,
                "_emit_frame_available",
                Qt.ConnectionType.QueuedConnection,
            )
        if brightness is not None:
            self.brightness_updated.emit(brightness)
        if focus_score is not None:
            self.on_focus_score_ready(focus_score)
        if recorder is not None:
            recorder.enqueue(frame)

    @Slot()
    def _emit_frame_available(self) -> None:
        with self._lock:
            self._ui_frame_pending = False
            self._ui_last_emit = time.monotonic()
        self.frame_available.emit()

    # Snapshot
    @Slot()
    def capture_snapshot(self) -> None:
        """Capture a full-resolution frame and save as a timestamped OME-TIFF."""
        snap_dir = self._snapshot_dir()
        snap_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        if self._image_store is not None:
            filename = self._image_store.new_image_path(
                "snapshot",
                "capture",
                objective=self._safe_objective(),
                captured_at=now,
            )
        else:
            ts = now.strftime("%Y%m%d_%H%M%S_%f")[:19]
            filename = snap_dir / f"microscope_{ts}.ome.tiff"
        self.capture_busy_changed.emit(True)
        threading.Thread(
            target=self._do_hires_snapshot_with_busy,
            args=(filename, now),
            daemon=True,
        ).start()

    def _do_hires_snapshot_with_busy(self, filename: Path, captured_at: datetime) -> None:
        try:
            self._do_hires_snapshot(filename, captured_at)
        finally:
            self.capture_busy_changed.emit(False)

    @Slot(str, result=bool)
    def capture_tile(self, path: str) -> bool:
        """Save the current frame to a specific path (used by tile scanner)."""
        try:
            import cv2
        except ImportError:
            return False
        frame = self.capture_native_frame()
        if frame is None:
            return False
        try:
            out = Path(path)
            out.parent.mkdir(parents=True, exist_ok=True)
            bgr = frame[:, :, ::-1]
            cv2.imwrite(str(out), bgr)
            return True
        except Exception as e:
            print(f"[tile] save failed: {e}")
            return False

    def _do_hires_snapshot(self, filename: Path, captured_at: datetime) -> None:
        frame = self.capture_native_frame()
        if frame is None:
            self.snapshot_failed.emit("no frame available")
            return
        if self._write_snapshot_ome(filename, frame, captured_at):
            self.snapshot_saved.emit(str(filename))
        else:
            self.snapshot_failed.emit("write failed")

    # Capture metadata
    def _snapshot_dir(self) -> Path:
        if self._image_store is not None:
            return self._image_store.snapshot_dir()
        return self._capture_root() / "snapshots"

    def _recording_dir(self) -> Path:
        if self._image_store is not None:
            return self._image_store.video_dir()
        return self._capture_root() / "videos"

    def _capture_root(self) -> Path:
        raw = self._config.get("captures.root", "")
        if isinstance(raw, str) and raw.strip() != "":
            return Path(raw).expanduser()
        return _DEFAULT_CAPTURE_ROOT

    def _safe_position(self) -> dict[str, int | None]:
        try:
            x, y, z = self._get_position()
            return {"x": int(x), "y": int(y), "z": int(z)}
        except Exception:
            return {"x": None, "y": None, "z": None}

    def _safe_objective(self) -> str:
        try:
            return str(self._get_objective() or "")
        except Exception:
            return ""

    def _snapshot_metadata(self, frame: np.ndarray, captured_at: datetime) -> dict:
        h, w = frame.shape[:2]
        metadata = {
            "version": 1,
            "type": "snapshot",
            "captured_at": captured_at.isoformat(timespec="seconds"),
            "objective": self._safe_objective(),
            "position": self._safe_position(),
            "width": int(w),
            "height": int(h),
            "resolution": {"width": int(w), "height": int(h)},
            "format": "OME-TIFF",
            "tags": [],
        }
        return metadata

    def _write_snapshot_ome(self, filename: Path, frame: np.ndarray, captured_at: datetime) -> bool:
        try:
            ome_tiff.write_snapshot(filename, frame, self._snapshot_metadata(frame, captured_at))
            return True
        except Exception as e:
            print(f"[snapshot] save failed: {e}")
            return False

    def _write_video_metadata(
        self,
        filename: Path,
        captured_at: datetime | None = None,
        started_monotonic: float | None = None,
        dims: tuple[int, int] | None = None,
        objective: str | None = None,
        position: dict[str, int | None] | None = None,
    ) -> None:
        if self._image_store is None:
            return

        capture_time = captured_at or datetime.now()
        duration = 0.0
        started = started_monotonic if started_monotonic is not None else 0.0
        if started > 0:
            duration = max(0.0, time.monotonic() - started)
        width, height = dims or (0, 0)

        metadata = {
            "version": 1,
            "type": "video",
            "captured_at": capture_time.isoformat(timespec="seconds"),
            "objective": objective or "",
            "position": position or {"x": None, "y": None, "z": None},
            "width": width,
            "height": height,
            "resolution": {"width": width, "height": height},
            "format": filename.suffix.lstrip(".").upper(),
            "duration_seconds": round(duration, 2),
            "tags": [],
        }
        self._image_store.write_metadata(filename, metadata)
