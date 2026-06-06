"""QQuickImageProvider for live camera feed."""

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

from retroscope.services import ome_tiff
from retroscope.services.camera_service import CameraService

_BLANK_RGB  = QImage(1, 1, QImage.Format.Format_RGB888)
_BLANK_RGB.fill(0)


class CameraImageProvider(QQuickImageProvider):
    """Serves camera frames to QML on demand."""

    def __init__(self, camera_service: CameraService) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._svc = camera_service

    def requestImage(self, id: str, size: QSize, requestedSize: QSize) -> QImage:
        frame = self._svc.get_latest_frame()
        if frame is None:
            return _BLANK_RGB.copy()

        h, w, ch = frame.shape
        if ch == 4:
            fmt = QImage.Format.Format_RGBA8888
            bpl = w * 4
        else:
            fmt = QImage.Format.Format_RGB888
            bpl = w * 3
        img = QImage(frame.data, w, h, bpl, fmt)
        return img.copy()


class OmeTiffImageProvider(QQuickImageProvider):
    """Serves OME-TIFF planes directly from captures."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, id: str, size: QSize, requestedSize: QSize) -> QImage:
        clean = id.split("?", 1)[0]
        parts = [p for p in clean.split("/") if p]
        if len(parts) < 2:
            return _BLANK_RGB.copy()
        try:
            path = ome_tiff.decode_ome_path(parts[0])
            ifd = int(parts[1])
            frame = ome_tiff.read_plane(path, ifd)
        except Exception:
            frame = None
        if frame is None:
            return _BLANK_RGB.copy()
        rw, rh = requestedSize.width(), requestedSize.height()
        if rw > 0 or rh > 0:
            h, w = frame.shape[:2]
            scale_w = rw / w if rw > 0 else float("inf")
            scale_h = rh / h if rh > 0 else float("inf")
            scale = min(scale_w, scale_h, 1.0)
            if scale < 1.0:
                frame = _resize_rgb(frame, max(1, round(w * scale)), max(1, round(h * scale)))
        h, w = frame.shape[:2]
        img = QImage(frame.data, w, h, w * 3, QImage.Format.Format_RGB888)
        return img.copy()


def _resize_rgb(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    try:
        import cv2

        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    except Exception:
        img = QImage(frame.data, frame.shape[1], frame.shape[0], frame.shape[1] * 3, QImage.Format.Format_RGB888)
        scaled = img.copy().scaled(width, height)
        ptr = scaled.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(scaled.height(), scaled.width(), 4)
        return np.ascontiguousarray(arr[:, :, :3])
