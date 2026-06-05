"""Qt camera bridge for direct low-latency preview (+ frame tap).

Note: Partially AI-generated (_sample_yuv420_to_rgb, _mapped_yuv420p_to_rgb, ...)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QMetaObject,
    QObject,
    Property,
    Qt,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import (
    QCamera,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaRecorder,
    QVideoFrame,
    QVideoSink,
)

from retroscope.services.camera_service import CameraService
from retroscope.domain.focus_metrics import grayscale_focus_score
from retroscope.platform import is_pi

logger = logging.getLogger(__name__)


class DirectCameraBridge(QObject):
    """Owns camera pipeline and mirrors frames into a QML VideoOutput."""

    frame_tap_changed = Signal()
    camera_format_changed = Signal()
    camera_capabilities_changed = Signal()
    camera_connected_changed = Signal(bool)
    frame_analysis_enabled_changed = Signal(bool)
    live_video_enabled_changed = Signal(bool)

    def __init__(
        self,
        camera_service: CameraService,
        enabled: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera_service = camera_service
        self._enabled = enabled
        self._camera: QCamera | None = None
        self._session: QMediaCaptureSession | None = None
        self._media_devices = QMediaDevices(self)
        self._input_sink: QVideoSink | None = None
        self._image_capture: QObject | None = None
        self._media_recorder: QMediaRecorder | None = None
        self._output_sink: QObject | None = None
        self._camera_connected = False
        self._active_device_key = ""
        self._stopping_camera = False
        self._last_tap_s = 0.0
        # Settings UI overwrites _tap_fps/_tap_width via setCameraFps/setCameraResolution
        self._tap_fps = 8
        self._tap_interval_s = 1.0 / self._tap_fps
        self._tap_width = 640
        self._camera_device = ""
        self._warned_conversion = False
        self._warned_image_capture = False
        self._warned_map_failure = False
        self._last_no_device_log_s = 0.0
        self._frame_tap_count = 0
        self._active_resolution = ""
        self._active_fps = 0.0
        self._available_resolutions: list[str] = []
        self._available_fps: list[int] = []
        self._frame_analysis_enabled = True
        self._live_video_enabled = True
        self._analysis_cond = threading.Condition()
        self._analysis_frame: tuple[object | None, np.ndarray | None] | None = None
        self._analysis_running = True
        self._analysis_thread = threading.Thread(
            target=self._analysis_worker_loop,
            daemon=True,
        )
        self._analysis_thread.start()
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(1000)
        self._reconnect_timer.timeout.connect(self._retry_camera_connection)
        self._media_devices.videoInputsChanged.connect(self._on_video_inputs_changed)
        # Hi-res capture queue
        self._hires_queue: deque[dict] = deque()
        self._hires_lock = threading.Lock()

    @Property(int, notify=frame_tap_changed)
    def frameTapCount(self) -> int:
        return self._frame_tap_count

    @Property(str, notify=camera_format_changed)
    def activeResolution(self) -> str:
        return self._active_resolution

    @Property(float, notify=camera_format_changed)
    def activeFps(self) -> float:
        return self._active_fps

    @Property(list, notify=camera_capabilities_changed)
    def availableResolutions(self) -> list[str]:
        return self._available_resolutions

    @Property(list, notify=camera_capabilities_changed)
    def availableFps(self) -> list[int]:
        return self._available_fps

    @Property(bool, notify=frame_analysis_enabled_changed)
    def frameAnalysisEnabled(self) -> bool:
        return self._frame_analysis_enabled

    @Slot(bool)
    def setFrameAnalysisEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._frame_analysis_enabled:
            return
        self._frame_analysis_enabled = enabled
        self._last_tap_s = 0.0
        if not enabled:
            with self._analysis_cond:
                self._analysis_frame = None
        self.frame_analysis_enabled_changed.emit(enabled)

    @Property(bool, notify=live_video_enabled_changed)
    def liveVideoEnabled(self) -> bool:
        return self._live_video_enabled

    @Slot(bool)
    def setLiveVideoEnabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._live_video_enabled:
            return
        self._live_video_enabled = enabled
        if not enabled and self._output_sink is not None:
            try:
                self._output_sink.setVideoFrame(QVideoFrame())
            except Exception:
                pass
        self.live_video_enabled_changed.emit(enabled)

    @Slot(str, str, int)
    def configureCamera(self, device: str, resolution: str, fps: int) -> None:
        device_changed = self._apply_camera_device(device)
        self._apply_analysis_settings(resolution, fps)
        if device_changed:
            self._restart_camera()

    @Slot(str)
    def setCameraDevice(self, device: str) -> None:
        if self._apply_camera_device(device):
            self._restart_camera()

    @Slot(str)
    def setCameraResolution(self, resolution: str) -> None:
        self._apply_analysis_settings(resolution, -1)

    @Slot(int)
    def setCameraFps(self, fps: int) -> None:
        self._apply_analysis_settings("", fps)

    def _apply_camera_device(self, device: str) -> bool:
        if device:
            clean_device = str(device).strip()
            if clean_device != self._camera_device:
                self._camera_device = clean_device
                return True
        return False

    def _apply_analysis_settings(self, resolution: str, fps: int) -> None:
        old_width = self._tap_width
        old_fps = self._tap_fps
        if resolution:
            parsed = self._parse_resolution(resolution)
            if parsed is not None:
                width, _height = parsed
                self._tap_width = max(160, width)
        if fps >= 0:
            self._tap_fps = max(1, int(fps))
            self._tap_interval_s = 1.0 / self._tap_fps
        if self._tap_width != old_width or self._tap_fps != old_fps:
            logger.info(
                f"[camera] direct analysis tap set to {self._tap_fps} fps @ {self._tap_width}px"
            )

    def _parse_resolution(self, resolution: str) -> tuple[int, int] | None:
        parts = str(resolution).lower().replace("×", "x").split("x", 1)
        if len(parts) != 2:
            return None
        try:
            width = int(parts[0].strip())
            height = int(parts[1].strip())
        except ValueError:
            return None
        if width <= 0 or height <= 0:
            return None
        return width, height

    @Slot(QObject)
    def setVideoSink(self, sink: QObject | None) -> None:
        if not self._enabled:
            return
        self._output_sink = sink
        if self._output_sink is None:
            logger.debug("[camera] direct bridge has no QML video sink yet")
            self._reconnect_timer.stop()
            return
        self._ensure_started()

    @Slot()
    def stop(self) -> None:
        self._enabled = False
        self._output_sink = None
        self._reconnect_timer.stop()
        self._stop_analysis_worker()
        self._stop_camera_pipeline(delete_later=True)
        self._flush_deferred_deletes()

    def _stop_analysis_worker(self) -> None:
        with self._analysis_cond:
            self._analysis_running = False
            self._analysis_frame = None
            self._analysis_cond.notify_all()
        if (
            self._analysis_thread.is_alive()
            and threading.current_thread() is not self._analysis_thread
        ):
            self._analysis_thread.join(timeout=1.0)

    def _flush_deferred_deletes(self) -> None:
        if QCoreApplication.instance() is None:
            return
        try:
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        except Exception:
            pass

    def _restart_camera(self) -> None:
        self._stop_camera_pipeline(delete_later=True)
        self._warned_conversion = False
        self._warned_image_capture = False
        self._warned_map_failure = False
        self._last_tap_s = 0.0
        if self._enabled and self._output_sink is not None:
            self._ensure_started()

    def _stop_camera_pipeline(self, delete_later: bool) -> None:
        self._stopping_camera = True
        if self._input_sink is not None:
            try:
                self._input_sink.videoFrameChanged.disconnect(self._on_video_frame)
            except (RuntimeError, TypeError):
                pass
        if self._image_capture is not None:
            try:
                self._image_capture.imageCaptured.disconnect(self._on_image_captured)
            except (RuntimeError, TypeError):
                pass
            try:
                self._image_capture.errorOccurred.disconnect(self._on_image_capture_error)
            except (RuntimeError, TypeError):
                pass
        if self._session is not None:
            try:
                self._session.setRecorder(None)
                self._session.setVideoSink(None)
                self._session.setImageCapture(None)
                self._session.setCamera(None)
            except Exception:
                pass
        if self._media_recorder is not None:
            try:
                self._media_recorder.recorderStateChanged.disconnect(self._on_recorder_state_changed)
            except (RuntimeError, TypeError):
                pass
            try:
                self._media_recorder.errorOccurred.disconnect(self._on_recorder_error)
            except (RuntimeError, TypeError):
                pass
            try:
                self._media_recorder.stop()
            except Exception:
                pass
        if self._camera is not None:
            try:
                self._camera.errorOccurred.disconnect(self._on_camera_error)
            except (RuntimeError, TypeError):
                pass
            try:
                self._camera.activeChanged.disconnect(self._on_camera_active_changed)
            except (RuntimeError, TypeError):
                pass
            try:
                self._camera.stop()
            except Exception:
                pass
        for obj in (self._input_sink, self._image_capture, self._media_recorder, self._session, self._camera):
            if obj is not None:
                try:
                    if delete_later:
                        obj.deleteLater()
                except Exception:
                    pass
        self._camera = None
        self._session = None
        self._input_sink = None
        self._image_capture = None
        self._media_recorder = None
        self._active_device_key = ""
        self._stopping_camera = False
        self._fail_all_hires("camera pipeline stopped")
        self._set_camera_connected(False)

    def _ensure_started(self) -> None:
        if self._camera is not None:
            self._reconnect_timer.stop()
            return

        device = self._select_camera_device()
        if device.isNull():
            self._log_no_video_input()
            self._set_camera_connected(False)
            self._start_reconnect_timer()
            return

        self._input_sink = QVideoSink(self)
        self._input_sink.videoFrameChanged.connect(self._on_video_frame)
        # QImageCapture is the only path to native-resolution stills
        from PySide6.QtMultimedia import QImageCapture

        self._image_capture = QImageCapture(self)
        self._image_capture.imageCaptured.connect(self._on_image_captured)
        self._image_capture.errorOccurred.connect(self._on_image_capture_error)
        self._media_recorder = QMediaRecorder(self)
        self._media_recorder.recorderStateChanged.connect(self._on_recorder_state_changed)
        self._media_recorder.errorOccurred.connect(self._on_recorder_error)

        self._camera = QCamera(device, self)
        self._camera.errorOccurred.connect(self._on_camera_error)
        self._camera.activeChanged.connect(self._on_camera_active_changed)
        selected_format = self._select_camera_format(device)
        if selected_format is not None:
            self._camera.setCameraFormat(selected_format)
        self._session = QMediaCaptureSession(self)
        self._session.setCamera(self._camera)
        self._session.setVideoSink(self._input_sink)
        if self._image_capture is not None:
            self._session.setImageCapture(self._image_capture)
        if self._media_recorder is not None:
            self._session.setRecorder(self._media_recorder)
        self._camera.start()
        self._active_device_key = self._device_key(device)
        self._update_active_format()
        self._set_camera_connected(True)
        self._reconnect_timer.stop()

    @Slot()
    def _retry_camera_connection(self) -> None:
        if not self._enabled or self._output_sink is None:
            self._reconnect_timer.stop()
            return
        if self._camera is not None:
            self._reconnect_timer.stop()
            return
        self._ensure_started()

    def _start_reconnect_timer(self) -> None:
        if self._enabled and self._output_sink is not None and not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    @Slot()
    def _on_video_inputs_changed(self) -> None:
        if not self._enabled or self._output_sink is None:
            return
        if self._camera is None:
            self._ensure_started()
            return
        keys = {self._device_key(device) for device in self._video_inputs()}
        if self._active_device_key and self._active_device_key not in keys:
            logger.info("[camera] No active video input, waiting for reconnect")
            self._stop_camera_pipeline(delete_later=True)
            self._start_reconnect_timer()

    @Slot()
    def _on_camera_active_changed(self) -> None:
        if self._stopping_camera or self._camera is None:
            return
        try:
            active = bool(self._camera.isActive())
        except Exception:
            active = False
        if active:
            self._set_camera_connected(True)
        elif self._camera_connected:
            logger.info("[camera] video input became inactive, waiting for reconnect")
            self._stop_camera_pipeline(delete_later=True)
            self._start_reconnect_timer()

    @Slot(object, str)
    def _on_camera_error(self, _error: object, message: str = "") -> None:
        if self._stopping_camera:
            return
        logger.info("[camera] video input error: %s", message or "unknown")
        self._stop_camera_pipeline(delete_later=True)
        self._start_reconnect_timer()

    @Slot(object)
    def _on_recorder_state_changed(self, state: object) -> None:
        try:
            stopped = state == QMediaRecorder.RecorderState.StoppedState
        except Exception:
            stopped = "Stopped" in str(state)
        if stopped:
            handler = getattr(self._camera_service, "on_recording_backend_stopped", None)
            if handler is not None:
                handler()

    @Slot(object, str)
    def _on_recorder_error(self, _error: object, message: str = "") -> None:
        logger.info("[recording] native recorder error: %s", message or "unknown")
        handler = getattr(self._camera_service, "on_recording_backend_stopped", None)
        if handler is not None:
            handler()

    def _set_camera_connected(self, connected: bool) -> None:
        connected = bool(connected)
        if not connected:
            handler = getattr(self._camera_service, "on_camera_disconnected", None)
            if handler is not None:
                handler()
        if connected == self._camera_connected:
            return
        self._camera_connected = connected
        self.camera_connected_changed.emit(connected)

    def start_recording_to(self, path: str) -> bool:
        if not self._enabled:
            return False
        self._ensure_started()
        if self._media_recorder is None:
            return False
        try:
            self._media_recorder.setOutputLocation(QUrl.fromLocalFile(path))
            self._media_recorder.record()
            return True
        except Exception as e:
            logger.warning("[recording] native Qt recorder failed to start: %s", e)
            return False

    def stop_recording(self) -> None:
        if self._media_recorder is None:
            return
        try:
            self._media_recorder.stop()
        except Exception as e:
            logger.warning("[recording] native Qt recorder failed to stop: %s", e)

    def recording_dimensions(self) -> tuple[int, int]:
        if self._active_resolution:
            parsed = self._parse_resolution(self._active_resolution)
            if parsed is not None:
                return parsed
        if self._camera is not None:
            width, height, _fps = self._format_geometry(self._camera.cameraFormat())
            return max(0, width), max(0, height)
        return 0, 0

    def native_capture_size(self) -> tuple[int, int]:
        """Return the expected still-capture size."""
        return self.recording_dimensions()

    def _select_camera_device(self) -> object:
        devices = self._video_inputs()
        requested = self._camera_device.strip()
        if requested.startswith("/dev/") and not is_pi():
            requested = ""
        if requested:
            for device in devices:
                if self._device_matches(device, requested):
                    logger.info("[camera] direct bridge selected device %s", self._device_label(device))
                    return device
            labels = ", ".join(self._device_label(d) for d in devices[:8])
            logger.info("[camera] requested device %r not found. Available: %s", requested, labels)
        return QMediaDevices.defaultVideoInput()

    def _video_inputs(self) -> list[object]:
        try:
            return list(QMediaDevices.videoInputs())
        except Exception:
            return []

    def _device_matches(self, device: object, requested: str) -> bool:
        requested_l = requested.lower()
        requested_tokens = {requested_l}
        if requested_l.startswith("/dev/"):
            requested_tokens.add(requested_l.rsplit("/", 1)[-1])
        label = self._device_label(device).lower()
        return any(token and token in label for token in requested_tokens)

    def _log_no_video_input(self) -> None:
        now = time.monotonic()
        if now - self._last_no_device_log_s < 5.0:
            return
        self._last_no_device_log_s = now
        dev_paths = self._video_device_paths()
        if dev_paths or is_pi():
            logger.info(
                "[camera] no Qt video input yet. /dev/video*: %s",
                ", ".join(dev_paths) if dev_paths else "none",
            )
        else:
            logger.info("[camera] direct bridge found no default video input")

    def _video_device_paths(self) -> list[str]:
        try:
            return sorted(str(path) for path in Path("/dev").glob("video*"))
        except Exception:
            return []

    def _device_label(self, device: object) -> str:
        parts: list[str] = []
        try:
            desc = str(device.description())
            if desc:
                parts.append(desc)
        except Exception:
            pass
        try:
            raw_id = device.id() 
            if hasattr(raw_id, "data"):
                raw_id = raw_id.data()
            if isinstance(raw_id, bytes):
                text_id = raw_id.decode(errors="replace")
            else:
                text_id = str(raw_id)
            if text_id:
                parts.append(text_id)
        except Exception:
            pass
        return " / ".join(parts) if parts else "unknown"

    def _device_key(self, device: object) -> str:
        try:
            raw_id = device.id()
            if hasattr(raw_id, "data"):
                raw_id = raw_id.data()
            if isinstance(raw_id, bytes):
                return raw_id.decode(errors="replace")
            return str(raw_id)
        except Exception:
            return self._device_label(device)

    def _update_active_format(self) -> None:
        if self._camera is None:
            return
        width, height, fps = self._format_geometry(self._camera.cameraFormat())
        self._active_resolution = f"{width}x{height}" if width > 0 and height > 0 else ""
        self._active_fps = fps
        self.camera_format_changed.emit()

    # Native-resolution still capture (used by snapshot, tile scan, focus stack)
    def capture_native_to_array_sync(
        self,
        timeout_s: float = 3.0,
        should_cancel=None,
    ) -> np.ndarray | None:
        """Capture one native-resolution frame as an RGB ndarray."""

        if self._image_capture is None:
            logger.info("[camera] hi-res capture unavailable: QImageCapture not created")
            return None
        entry: dict = {"event": threading.Event(), "image": None}
        with self._hires_lock:
            self._hires_queue.append(entry)

        QMetaObject.invokeMethod(
            self,
            "_trigger_hires_internal",
            Qt.ConnectionType.QueuedConnection,
        )
        deadline = time.monotonic() + max(0.0, timeout_s)
        got = False
        while time.monotonic() < deadline:
            if entry["event"].wait(0.15):
                got = True
                break
            if should_cancel is not None and should_cancel():
                break
        if not got:
            with self._hires_lock:
                try:
                    self._hires_queue.remove(entry)
                except ValueError:
                    pass
            logger.info("[camera] native still capture aborted/timed out")
            return None
        image: QImage | None = entry["image"]
        if image is None or image.isNull():
            logger.info("[camera] hi-res capture returned null QImage")
            return None
        logger.info(
            "[camera] hi-res capture delivered QImage %dx%d",
            image.width(), image.height(),
        )
        return self._qimage_to_rgb_array(image)

    @Slot()
    def _trigger_hires_internal(self) -> None:
        """Runs on the bridge thread. Triggers QImageCapture.capture()."""
        if self._image_capture is None:
            self._fail_oldest_hires("image capture unavailable")
            return
        try:
            self._image_capture.capture()
        except Exception as e:
            logger.info("[camera] native still capture trigger failed: %s", e)
            self._fail_oldest_hires(str(e))

    def _fail_oldest_hires(self, _reason: str) -> None:
        with self._hires_lock:
            if not self._hires_queue:
                return
            entry = self._hires_queue.popleft()
        entry["image"] = None
        entry["event"].set()

    def _fail_all_hires(self, _reason: str) -> None:
        with self._hires_lock:
            entries = list(self._hires_queue)
            self._hires_queue.clear()
        for entry in entries:
            entry["image"] = None
            entry["event"].set()

    @Slot(int, QImage)
    def _on_image_captured(self, _request_id: int, image: QImage) -> None:
        with self._hires_lock:
            entry = self._hires_queue.popleft() if self._hires_queue else None
        if entry is None:
            return
        entry["image"] = QImage(image) if not image.isNull() else None
        entry["event"].set()

    @Slot(int, object, str)
    def _on_image_capture_error(self, _request_id: int, _error: object, message: str) -> None:
        with self._hires_lock:
            entry = self._hires_queue.popleft() if self._hires_queue else None
        if entry is not None:
            entry["image"] = None
            entry["event"].set()
            return
        if not self._warned_image_capture:
            logger.info("[camera] direct hi-res capture error: %s", message)
            self._warned_image_capture = True

    def _select_camera_format(self, device: object) -> object | None:
        try:
            formats = list(device.videoFormats())
        except Exception:
            formats = []
        if not formats:
            logger.info("[camera] direct bridge found no selectable camera formats")
            return None

        self._update_available_formats(formats)

        best = max(formats, key=lambda fmt: self._format_geometry(fmt)[0] * self._format_geometry(fmt)[1])
        target_w, target_h, _target_fps = self._format_geometry(best)
        target_area = target_w * target_h
        target_aspect = target_w / max(1, target_h)

        labels = [self._format_label(fmt) for fmt in formats]
        logger.debug("[camera] direct bridge available formats: %s", ", ".join(labels[:12]))
        if len(labels) > 12:
            logger.debug("[camera] direct bridge has %s formats total", len(labels))

        def score(fmt: object) -> tuple[float, float, float, float, float]:
            width, height, max_fps = self._format_geometry(fmt)
            area = width * height
            size_delta = (target_area - area) / max(1, target_area)
            aspect_delta = abs((width / max(1, height)) - target_aspect)
            pixel_delta = self._format_pixel_score(fmt)
            fps_delta = -max_fps
            return (0, size_delta, aspect_delta, pixel_delta, fps_delta)

        selected = min(formats, key=score)
        logger.info(
            "[camera] direct bridge selected format %s",
            self._format_label(selected),
        )
        return selected

    def _update_available_formats(self, formats: list[object]) -> None:
        new_resolutions = ["1280x720", "960x540", "640x360"]
        new_fps = [10, 8, 4, 2]
        if new_resolutions != self._available_resolutions or new_fps != self._available_fps:
            self._available_resolutions = new_resolutions
            self._available_fps = new_fps
            self.camera_capabilities_changed.emit()

    def _format_geometry(self, fmt: object) -> tuple[int, int, float]:
        try:
            size = fmt.resolution() 
            width, height = int(size.width()), int(size.height())
        except Exception:
            width, height = 0, 0
        try:
            max_fps = float(fmt.maxFrameRate())
        except Exception:
            max_fps = 0.0
        return width, height, max_fps

    def _format_label(self, fmt: object) -> str:
        width, height, max_fps = self._format_geometry(fmt)
        try:
            min_fps = float(fmt.minFrameRate())
        except Exception:
            min_fps = max_fps
        fps_label = f"{max_fps:.0f}fps" if min_fps == max_fps else f"{min_fps:.0f}-{max_fps:.0f}fps"
        pixel = self._pixel_format_name(self._format_pixel_format(fmt))
        return f"{width}x{height}@{fps_label}/{pixel}"

    def _format_pixel_format(self, fmt: object) -> object | None:
        try:
            return fmt.pixelFormat()
        except Exception:
            return None

    def _format_pixel_score(self, fmt: object) -> int:
        name = self._pixel_format_name(self._format_pixel_format(fmt)).lower()
        if "yuv420p" in name or "yv12" in name or "yu12" in name:
            return 0
        if "nv12" in name or "nv21" in name:
            return 1
        if "rgb" in name or "bgr" in name:
            return 2
        return 3

    def _pixel_format_name(self, pixel_format: object | None) -> str:
        if pixel_format is None:
            return "unknown"
        name = getattr(pixel_format, "name", None)
        if isinstance(name, str):
            return name.replace("Format_", "")
        text = str(pixel_format)
        if "." in text:
            text = text.rsplit(".", 1)[-1]
        return text.replace("Format_", "")

    @Slot(object)
    def _on_video_frame(self, frame: object) -> None:
        now = time.monotonic()
        should_tap = self._frame_analysis_enabled and now - self._last_tap_s >= self._tap_interval_s
        if should_tap:
            self._last_tap_s = now
            self._enqueue_analysis_frame(frame, self._copy_focus_plane_from_frame(frame))

        if self._live_video_enabled and self._output_sink is not None:
            try:
                self._output_sink.setVideoFrame(frame)
            except Exception as e:
                logger.info("[camera] direct preview sink forward failed: %s", e)
                self._output_sink = None

    def _enqueue_analysis_frame(self, frame: object, focus_plane: np.ndarray | None) -> None:
        try:
            analysis_frame = QVideoFrame(frame)
        except Exception:
            analysis_frame = frame
        with self._analysis_cond:
            if not self._analysis_running:
                return
            self._analysis_frame = (analysis_frame, focus_plane)
            self._analysis_cond.notify()

    def _analysis_worker_loop(self) -> None:
        while True:
            with self._analysis_cond:
                while self._analysis_frame is None and self._analysis_running:
                    self._analysis_cond.wait()
                if not self._analysis_running:
                    return
                frame, focus_plane = self._analysis_frame
                self._analysis_frame = None

            if not self._frame_analysis_enabled:
                continue
            if focus_plane is not None:
                self._publish_focus_plane(focus_plane)
            arr, _focus_score = self._frame_to_rgb_array_and_focus(frame, compute_focus=False)
            if not self._frame_analysis_enabled:
                continue

            if arr is None:
                if not self._warned_conversion:
                    logger.info("[camera] direct bridge could not convert QVideoFrame")
                    self._warned_conversion = True
                continue

            self._publish_analysis_frame(arr)

    def _publish_analysis_frame(self, arr: np.ndarray) -> None:
        self._frame_tap_count += 1
        if self._frame_tap_count <= 3 or self._frame_tap_count % 120 == 0:
            logger.debug(
                "[camera] direct bridge tapped frame %s: %sx%s",
                self._frame_tap_count,
                arr.shape[1],
                arr.shape[0],
            )
        self.frame_tap_changed.emit()
        self._camera_service.on_frame_ready(arr)

    def _frame_to_rgb_array_and_focus(
        self,
        frame: object,
        compute_focus: bool = True,
    ) -> tuple[np.ndarray | None, float | None]:
        mapped = self._map_frame_to_rgb_array(frame, compute_focus=compute_focus)
        if mapped is not None:
            return mapped

        try:
            image = frame.toImage()
        except Exception:
            image = QImage()
        if image.isNull():
            return None, None
        focus_score = self._focus_score_from_qimage(image) if compute_focus else None
        if image.width() > self._tap_width:
            height = max(1, int(image.height() * self._tap_width / max(1, image.width())))
            image = image.scaled(self._tap_width, height)
        return self._qimage_to_rgb_array(image), focus_score

    def _copy_focus_plane_from_frame(self, frame: object) -> np.ndarray | None:
        try:
            pixel = self._pixel_format_name(frame.surfaceFormat().pixelFormat()).lower()
            width = int(frame.width())
            height = int(frame.height())
        except Exception:
            pixel = ""
            width = 0
            height = 0

        if width > 0 and height > 0 and (
            "nv12" in pixel
            or "nv21" in pixel
            or "yuv420p" in pixel
            or "yu12" in pixel
            or "yv12" in pixel
        ):
            try:
                map_mode = getattr(getattr(QVideoFrame, "MapMode", QVideoFrame), "ReadOnly")
                if frame.map(map_mode):
                    try:
                        y = self._mapped_plane(frame, 0, height, width)
                        if y is not None:
                            return np.array(y, copy=True)
                    finally:
                        try:
                            frame.unmap()
                        except Exception:
                            pass
            except Exception:
                pass

        return None

    def _publish_focus_plane(self, focus_plane: np.ndarray) -> None:
        focus_score = self._focus_score_from_plane(focus_plane)
        if focus_score is not None:
            self._camera_service.on_focus_score_ready(focus_score)

    def _focus_score_from_plane(self, focus_plane: np.ndarray) -> float | None:
        return grayscale_focus_score(focus_plane, roi=0.15)

    def _map_frame_to_rgb_array(
        self,
        frame: object,
        compute_focus: bool = True,
    ) -> tuple[np.ndarray, float | None] | None:
        try:
            pixel = self._pixel_format_name(frame.surfaceFormat().pixelFormat()).lower()
            width = int(frame.width())
            height = int(frame.height()) 
        except Exception:
            return None
        if width <= 0 or height <= 0:
            return None

        try:
            map_mode = getattr(getattr(QVideoFrame, "MapMode", QVideoFrame), "ReadOnly")
            if not frame.map(map_mode):
                self._note_frame_map_failure()
                return None
        except Exception:
            self._note_frame_map_failure()
            return None

        try:
            if "nv12" in pixel or "nv21" in pixel:
                return self._mapped_nv12_to_rgb(
                    frame,
                    width,
                    height,
                    swap_uv="nv21" in pixel,
                    compute_focus=compute_focus,
                )
            if "yuv420p" in pixel or "yu12" in pixel:
                return self._mapped_yuv420p_to_rgb(
                    frame,
                    width,
                    height,
                    swap_uv=False,
                    compute_focus=compute_focus,
                )
            if "yv12" in pixel:
                return self._mapped_yuv420p_to_rgb(
                    frame,
                    width,
                    height,
                    swap_uv=True,
                    compute_focus=compute_focus,
                )
        finally:
            try:
                frame.unmap()
            except Exception:
                pass
        return None

    def _note_frame_map_failure(self) -> None:
        if not self._warned_map_failure:
            logger.warning(
                "[camera] direct video frames are not CPU-mappable, falling back to QVideoFrame.toImage() for analysis"
            )
            self._warned_map_failure = True

    def _mapped_nv12_to_rgb(
        self,
        frame: object,
        width: int,
        height: int,
        swap_uv: bool,
        compute_focus: bool = True,
    ) -> tuple[np.ndarray, float] | None:
        uv_h = max(1, height // 2)
        y = self._mapped_plane(frame, 0, height, width)
        uv = self._mapped_plane(frame, 1, uv_h, width)
        if y is None or uv is None or uv.shape[1] < 2:
            return None
        focus_score = grayscale_focus_score(y, roi=0.15) if compute_focus else None
        u = uv[:, 1::2] if swap_uv else uv[:, 0::2]
        v = uv[:, 0::2] if swap_uv else uv[:, 1::2]
        rgb = self._sample_yuv420_to_rgb(y, u, v, width, height)
        return (rgb, focus_score) if rgb is not None else None

    def _mapped_yuv420p_to_rgb(
        self,
        frame: object,
        width: int,
        height: int,
        swap_uv: bool,
        compute_focus: bool = True,
    ) -> tuple[np.ndarray, float] | None:
        uv_w = max(1, width // 2)
        uv_h = max(1, height // 2)
        y = self._mapped_plane(frame, 0, height, width)
        first = self._mapped_plane(frame, 1, uv_h, uv_w)
        second = self._mapped_plane(frame, 2, uv_h, uv_w)
        if y is None or first is None or second is None:
            return None
        focus_score = grayscale_focus_score(y, roi=0.15) if compute_focus else None
        u, v = (second, first) if swap_uv else (first, second)
        rgb = self._sample_yuv420_to_rgb(y, u, v, width, height)
        return (rgb, focus_score) if rgb is not None else None

    def _mapped_plane(
        self,
        frame: object,
        plane: int,
        rows: int,
        cols: int,
    ) -> np.ndarray | None:
        try:
            line = int(frame.bytesPerLine(plane))
        except Exception:
            line = cols
        if line <= 0:
            line = cols
        try:
            count = int(frame.mappedBytes(plane))
        except Exception:
            count = line * rows
        needed = line * rows
        if count < needed:
            return None
        try:
            try:
                buf = frame.bits(plane)
            except TypeError:
                buf = frame.bits()
            raw = np.frombuffer(buf, dtype=np.uint8, count=count)
            if raw.size < needed:
                return None
            return raw[:needed].reshape(rows, line)[:, :cols]
        except Exception:
            return None

    def _sample_yuv420_to_rgb(
        self,
        y: np.ndarray,
        u: np.ndarray,
        v: np.ndarray,
        width: int,
        height: int,
    ) -> np.ndarray | None:
        out_w = min(self._tap_width, width)
        out_h = max(1, int(height * out_w / max(1, width)))
        if out_w <= 0 or out_h <= 0:
            return None

        xs = np.minimum((np.arange(out_w, dtype=np.int32) * width) // out_w, width - 1)
        ys = np.minimum((np.arange(out_h, dtype=np.int32) * height) // out_h, height - 1)
        uv_xs = np.minimum(xs // 2, u.shape[1] - 1)
        uv_ys = np.minimum(ys // 2, u.shape[0] - 1)

        yy = y[ys[:, None], xs[None, :]].astype(np.float32)
        uu = u[uv_ys[:, None], uv_xs[None, :]].astype(np.float32)
        vv = v[uv_ys[:, None], uv_xs[None, :]].astype(np.float32)

        c = yy - 16.0
        d = uu - 128.0
        e = vv - 128.0
        r = 1.164 * c + 1.596 * e
        g = 1.164 * c - 0.392 * d - 0.813 * e
        b = 1.164 * c + 2.017 * d
        rgb = np.stack((r, g, b), axis=2)
        return np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))

    def _qimage_to_rgb_array(self, image: QImage) -> np.ndarray | None:
        rgb = image.convertToFormat(QImage.Format.Format_RGB888)
        width, height = rgb.width(), rgb.height()
        bytes_per_line = rgb.bytesPerLine()
        if width <= 0 or height <= 0 or bytes_per_line < width * 3:
            return None

        try:
            raw = np.frombuffer(rgb.bits(), dtype=np.uint8, count=height * bytes_per_line)
            rows = raw.reshape(height, bytes_per_line)
            packed = rows[:, : width * 3].reshape(height, width, 3)
            return np.array(packed, copy=True)
        except Exception:
            return None

    def _focus_score_from_qimage(self, image: QImage) -> float | None:
        arr = self._qimage_to_rgb_array(image)
        if arr is None:
            return None
        gray = (
            0.299 * arr[:, :, 0].astype(np.float32)
            + 0.587 * arr[:, :, 1].astype(np.float32)
            + 0.114 * arr[:, :, 2].astype(np.float32)
        ).astype(np.uint8)
        return grayscale_focus_score(gray, roi=0.15)
