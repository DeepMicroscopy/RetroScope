"""Focus stacking service: Sweeps Z in configured steps, captures each plane, blends them and saves the result as one OME-TIFF."""

from __future__ import annotations

import threading
import time
from datetime import datetime

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.domain.focus_blending import DEFAULT_PYRAMID_LEVELS, pyramid_blend
from retroscope.services import ome_tiff
from retroscope.services.worker_lifecycle import PausableWorkerLifecycle

_MOVE_START_S = 0.80   # wait after moving to sweep start


class _FocusStackerWorker(QThread):
    """Background thread that executes the Z sweep and blending."""

    progress       = Signal(float)       # 0.0–1.0
    frame_captured = Signal(int, int)    # (current, total)
    finished       = Signal(str)         # output file path (empty on cancel)

    def __init__(
        self,
        camera_svc,
        motion_ctrl,
        image_store,
        objective_mgr,
        z_half_range: int,
        step_size: int,
        settle_ms: int,
        blending: str,
        get_position=None,
        z_start_abs: int | None = None,
        z_end_abs: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._camera      = camera_svc
        self._motion      = motion_ctrl
        self._image_store = image_store
        self._obj         = objective_mgr
        self._z_half      = z_half_range
        self._step        = step_size
        self._settle      = settle_ms / 1000.0
        self._blending    = blending
        self._get_pos     = get_position
        self._z_start_abs = z_start_abs
        self._z_end_abs   = z_end_abs
        self._cancel      = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def request_cancel(self) -> None:
        self._cancel = True
        self._pause_event.set()

    def request_pause(self) -> None:
        self._pause_event.clear()

    def request_resume(self) -> None:
        self._pause_event.set()

    def run(self) -> None:
        if self._z_start_abs is not None and self._z_end_abs is not None and self._get_pos is not None:
            try:
                current_z = self._get_pos()[2]
            except Exception:
                current_z = 0
            rel_start = self._z_start_abs - current_z
            rel_end   = self._z_end_abs   - current_z
            step = self._step if rel_end >= rel_start else -self._step
            positions = list(range(rel_start, rel_end + step, step))
        else:
            positions = list(range(-self._z_half, self._z_half + 1, self._step))
        total = len(positions)
        if total == 0:
            self.finished.emit("")
            return

        # Capture XYZ before any movement
        start_pos: tuple[int, int, int] | None = None
        if self._get_pos is not None:
            try:
                start_pos = self._get_pos()
            except Exception:
                pass

        frames: list[np.ndarray] = []

        # Move to start position
        self._motion.move_z(positions[0])
        time.sleep(_MOVE_START_S)

        accumulated = positions[0]
        captured_positions: list[int] = []

        for i, pos in enumerate(positions):
            if self._cancel:
                self._motion.move_z(-accumulated)
                self.finished.emit("")
                return

            frame = self._capture_frame()
            if frame is not None:
                frames.append(frame)
                captured_positions.append(int(pos))

            self.frame_captured.emit(i + 1, total)
            self.progress.emit((i + 1) / total)

            if i < total - 1:
                delta = positions[i + 1] - pos
                self._motion.move_z(delta)
                accumulated += delta
                time.sleep(self._settle)

            # Pause checkpoint
            self._pause_event.wait()
            if self._cancel:
                self._motion.move_z(-accumulated)
                self.finished.emit("")
                return

        # Return to origin
        self._motion.move_z(-accumulated)

        if not frames:
            print("[focus_stack] no frames captured. Aborting.")
            self.finished.emit("")
            return

        reference_shape = frames[0].shape
        if any(f.shape != reference_shape for f in frames):
            shapes = {f.shape for f in frames}
            print(
                f"[focus_stack] captured frames have inconsistent shapes ({shapes}). Aborting before blend."
            )
            self.finished.emit("")
            return

        # Blend frames
        try:
            blended = frames[0] if len(frames) == 1 else self._blend(frames)
        except Exception as e:
            print(f"[focus_stack] blend failed: {e}")
            self.finished.emit("")
            return

        # Save blended result and source planes into one OME-TIFF.
        path = self._save_result(blended, frames, captured_positions, start_pos)
        self.finished.emit(path)

    def _capture_frame(self) -> np.ndarray | None:
        if hasattr(self._camera, "capture_native_frame"):
            for attempt in range(2):
                arr = self._camera.capture_native_frame(
                    should_cancel=lambda: self._cancel,
                    allow_tap_fallback=False,
                )
                if arr is not None:
                    return arr
                if self._cancel:
                    return None
                time.sleep(0.05)
            return None   # Will skip and abort if too few frames
        if hasattr(self._camera, "wait_for_next_frame"):
            return self._camera.wait_for_next_frame(timeout=0.8)
        frame = self._camera.get_latest_frame()
        return frame.copy() if frame is not None else None

    def _save_result(
        self,
        blended: np.ndarray,
        frames: list[np.ndarray],
        z_positions: list[int],
        start_pos: "tuple[int,int,int] | None" = None,
    ) -> str:
        objective = self._obj.active_objective if self._obj is not None else ""
        path = self._image_store.new_image_path("stack", "stack", objective=objective)
        try:
            h, w = blended.shape[:2]
            metadata: dict = {
                "version": 1,
                "type": "stack",
                "captured_at": datetime.now().isoformat(timespec="seconds"),
                "objective": objective,
                "width": w,
                "height": h,
                "resolution": {"width": w, "height": h},
                "format": "OME-TIFF",
                "tags": [],
            }
            metadata["step_size"] = self._step
            if start_pos is not None:
                px, py, pz = start_pos
                metadata["position"] = {"x": px, "y": py, "z": pz}
                metadata["z_half_range"] = self._z_half
            ome_tiff.write_focus_stack(path, blended, frames, metadata, z_positions)
        except Exception as e:
            print(f"[focus_stack] save failed: {e}")
            return ""
        return str(path)

    def _blend(self, frames: list[np.ndarray]) -> np.ndarray:
        return pyramid_blend(frames, levels=DEFAULT_PYRAMID_LEVELS)


class FocusStackerService(QObject):
    """Manages the focus stacker worker lifecycle and exposes state."""

    busy_changed   = Signal(bool)
    paused_changed = Signal(bool)
    progress       = Signal(float)
    frame_captured = Signal(int, int)
    finished       = Signal(str)

    def __init__(
        self,
        camera_svc,
        motion_ctrl,
        image_store,
        objective_mgr,
        get_position=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera       = camera_svc
        self._motion       = motion_ctrl
        self._image_store  = image_store
        self._obj          = objective_mgr
        self._get_pos      = get_position
        self._lifecycle = PausableWorkerLifecycle(self.busy_changed, self.paused_changed)

    @property
    def busy(self) -> bool:
        return self._lifecycle.busy

    @property
    def paused(self) -> bool:
        return self._lifecycle.paused

    @Slot()
    def start(
        self,
        z_half_range: int = 50,
        step_size: int = 5,
        settle_ms: int = 150,
        blending: str = "laplacian",
        z_start_abs: int | None = None,
        z_end_abs: int | None = None,
    ) -> None:
        if self._lifecycle.busy:
            return
        worker = _FocusStackerWorker(
            self._camera,
            self._motion,
            self._image_store,
            self._obj,
            z_half_range,
            step_size,
            settle_ms,
            blending,
            get_position=self._get_pos,
            z_start_abs=z_start_abs,
            z_end_abs=z_end_abs,
        )
        worker.progress.connect(self.progress)
        worker.frame_captured.connect(self.frame_captured)
        worker.finished.connect(self._on_finished)
        self._lifecycle.start(worker)

    @Slot()
    def cancel(self) -> None:
        self._lifecycle.cancel()

    @Slot()
    def pause(self) -> None:
        self._lifecycle.pause()

    @Slot()
    def resume(self) -> None:
        self._lifecycle.resume()

    def _on_finished(self, path: str) -> None:
        self._lifecycle.finish()
        self.finished.emit(path)
