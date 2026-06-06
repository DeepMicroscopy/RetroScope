"""Tile scanning service: Scans a XY grid, optionally autofocuses each tile and captures snapshots."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.services import ome_tiff
from retroscope.services.stage_calibration import tile_steps_for_frame

_MOVE_START_S  = 0.50   # seconds to wait after moving to first tile
_AF_TIMEOUT_S  = 30.0   # max seconds to wait for per-tile autofocus
_OUTPUT_MOSAIC = "mosaic"
_OUTPUT_STITCH = "stitch"


def _serpentine_order(cols: int, rows: int) -> list[tuple[int, int]]:
    order = []
    for row in range(rows):
        col_range = range(cols) if row % 2 == 0 else range(cols - 1, -1, -1)
        for col in col_range:
            order.append((col, row))
    return order


def _raster_order(cols: int, rows: int) -> list[tuple[int, int]]:
    return [(col, row) for row in range(rows) for col in range(cols)]


class _TileScannerWorker(QThread):
    """Background thread that executes the tile grid scan."""

    progress        = Signal(float)       # 0.0–1.0
    tile_started    = Signal(int, int)    # (col, row)
    tile_done       = Signal(int, int)    # (col, row)
    finished        = Signal()
    stitch_started  = Signal()
    stitch_progress = Signal(float)
    stitch_finished = Signal(str)
    scan_saved      = Signal(str)

    def __init__(
        self,
        camera_svc,
        motion_ctrl,
        autofocus_svc,
        image_store,
        objective_mgr,
        get_position: Callable[[], tuple[int, int, int]] | None,
        cols: int,
        rows: int,
        overlap: float,
        pattern: str,
        autofocus_each: bool,
        record_video: bool,
        session_dir: Path | None = None,
        stitch_after: bool = False,
        settle_ms: int = 300,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._camera        = camera_svc
        self._motion        = motion_ctrl
        self._autofocus     = autofocus_svc
        self._image_store   = image_store
        self._obj           = objective_mgr
        self._get_position  = get_position or (lambda: (0, 0, 0))
        self._cols          = cols
        self._rows          = rows
        self._overlap       = overlap
        self._pattern       = pattern
        self._autofocus_each = autofocus_each
        self._record_video  = record_video
        self._session_dir   = session_dir
        self._stitch_after  = stitch_after
        self._settle        = settle_ms / 1000.0
        self._cancel        = False
        self._pause_event   = threading.Event()
        self._pause_event.set()

    def request_cancel(self) -> None:
        self._cancel = True
        self._pause_event.set()
        try:
            if self._autofocus is not None and self._autofocus.busy:
                self._autofocus.cancel()
        except Exception:
            pass

    def request_pause(self) -> None:
        self._pause_event.clear()

    def request_resume(self) -> None:
        self._pause_event.set()

    def run(self) -> None:
        profile = self._obj.current_profile()
        calibration_frame_w, calibration_frame_h = self._calibration_frame_size_px()
        stage_x, stage_y = self._stage_scale_um_per_step()
        tile_step = tile_steps_for_frame(
            calibration_frame_w,
            calibration_frame_h,
            profile.um_per_pixel,
            self._overlap,
            stage_x,
            stage_y,
        )
        step_x = tile_step.x_steps
        step_y = tile_step.y_steps

        if self._pattern == "serpentine":
            order = _serpentine_order(self._cols, self._rows)
        else:
            order = _raster_order(self._cols, self._rows)

        total = len(order)
        if total == 0:
            self.finished.emit()
            return

        if not self._preflight_soft_limits(order, step_x, step_y):
            self.finished.emit()
            return

        if self._record_video:
            self._run_video_scan(order, step_x, step_y, total)
            self.finished.emit()
            return

        tiles: list[dict] = []
        prev_col, prev_row = 0, 0
        accumulated_x, accumulated_y = 0, 0

        time.sleep(_MOVE_START_S)

        for i, (col, row) in enumerate(order):
            if self._cancel:
                break

            # Move to this tile
            dx = (col - prev_col) * step_x
            dy = (row - prev_row) * step_y
            if dx != 0 or dy != 0:
                move_ok = self._move_rel_blocking(dx, dy, 0)
                if move_ok is False:
                    self._cancel = True
                    break
                accumulated_x += dx
                accumulated_y += dy
                time.sleep(self._settle)

            prev_col, prev_row = col, row

            self.tile_started.emit(col, row)

            # Optional autofocus
            if self._autofocus_each and not self._cancel:
                self._run_autofocus_and_wait()

            if not self._cancel:
                frame = self._capture_frame()
                if frame is not None:
                    tiles.append(
                        {
                            "col": col,
                            "row": row,
                            "frame": frame,
                            "position": self._position_dict(),
                        }
                    )

            self.tile_done.emit(col, row)
            self.progress.emit((i + 1) / total)

            # Check pause (blocks here while paused)
            self._pause_event.wait()

            if self._cancel:
                break

        # Return home
        if accumulated_x != 0 or accumulated_y != 0:
            dx = -accumulated_x
            dy = -accumulated_y
            move_ok = self._move_rel_blocking(dx, dy, 0)
            if move_ok is False:
                self._cancel = True

        if not self._cancel and tiles:
            path = self._save_scan(tiles)
            self.scan_saved.emit(path)
            if self._stitch_after:
                self.stitch_finished.emit(path)

        self.finished.emit()

    def _run_video_scan(self, order: list[tuple[int, int]], step_x: int, step_y: int, total: int) -> None:
        del order
        already_recording = False
        if hasattr(self._camera, "is_recording"):
            try:
                already_recording = bool(self._camera.is_recording())
            except Exception:
                already_recording = False
        if not already_recording and hasattr(self._camera, "start_recording"):
            self._camera.start_recording()

        try:
            segments = self._video_scan_segments(step_x, step_y)
            completed = 0
            for dx, dy, tile_equivalent in segments:
                if self._cancel:
                    break
                if dx != 0 or dy != 0:
                    move_ok = self._motion.move_rel(dx, dy, 0, source="automation")
                    if move_ok is False:
                        self._cancel = True
                        break
                    self._sleep_for_video_segment(dx, dy)
                completed = min(total, completed + tile_equivalent)
                self.progress.emit(completed / max(1, total))
                self._pause_event.wait()
        finally:
            if not already_recording and hasattr(self._camera, "stop_recording"):
                self._camera.stop_recording()

    def _video_scan_segments(self, step_x: int, step_y: int) -> list[tuple[int, int, int]]:
        segments: list[tuple[int, int, int]] = []
        if self._cols <= 1 and self._rows <= 1:
            return segments
        if self._cols <= 1:
            segments.append((0, 0, 1))
            for _row in range(self._rows - 1):
                segments.append((0, step_y, 1))
            return segments

        if self._pattern == "serpentine":
            direction = 1
            for row in range(self._rows):
                segments.append((direction * step_x * (self._cols - 1), 0, self._cols))
                if row < self._rows - 1:
                    segments.append((0, step_y, 0))
                    direction *= -1
        else:
            for row in range(self._rows):
                segments.append((step_x * (self._cols - 1), 0, self._cols))
                if row < self._rows - 1:
                    segments.append((-step_x * (self._cols - 1), step_y, 0))
        return segments

    def _sleep_for_video_segment(self, dx: int, dy: int) -> None:
        profile = self._obj.current_profile()
        speed_x, speed_y = self._derived_pan_steps_per_second_xy(profile)
        x_seconds = abs(int(dx)) / max(1.0, speed_x) if dx else 0.0
        y_seconds = abs(int(dy)) / max(1.0, speed_y) if dy else 0.0
        time.sleep(max(x_seconds, y_seconds))

    def _derived_pan_steps_per_second_xy(self, profile) -> tuple[float, float]:
        config = getattr(self._obj, "_config", None)
        px_per_sec = 400.0
        if config is not None:
            try:
                px_per_sec = max(1.0, float(config.get("input.max_pan_speed_px_per_sec", 400)))
            except Exception:
                pass
        stage_x, stage_y = self._stage_scale_um_per_step()
        if stage_x <= 0.0 and stage_y > 0.0:
            stage_x = stage_y
        if stage_y <= 0.0 and stage_x > 0.0:
            stage_y = stage_x
        if stage_x <= 0.0:
            stage_x = 1.0
        if stage_y <= 0.0:
            stage_y = 1.0
        um_per_pixel = max(1e-6, float(profile.um_per_pixel))
        return (
            px_per_sec * um_per_pixel / max(1e-6, stage_x),
            px_per_sec * um_per_pixel / max(1e-6, stage_y),
        )

    def _save_scan(self, tiles: list[dict]) -> str:
        self.stitch_started.emit()
        requested_mode = self._requested_output_mode()
        stitched, actual_mode = self._render_scan_result(tiles)
        self.stitch_progress.emit(0.95)
        objective = self._obj.active_objective if self._obj is not None else ""
        path = self._image_store.new_image_path("stitch", "scan", objective=objective)
        try:
            metadata = self._scan_metadata(
                stitched,
                len(tiles),
                requested_mode=requested_mode,
                actual_mode=actual_mode,
            )
            ome_tiff.write_tile_scan(path, stitched, tiles, metadata)
            self.stitch_progress.emit(1.0)
            return str(path)
        except Exception as e:
            print(f"[tile_scan] save failed: {e}")
            return ""

    def _capture_frame(self) -> np.ndarray | None:
        # Tile scans need every tile at the same native resolution so the stitch (hopefully) lines up
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
            return None
        if hasattr(self._camera, "wait_for_next_frame"):
            return self._camera.wait_for_next_frame(timeout=0.8)
        frame = self._camera.get_latest_frame()
        return frame.copy() if frame is not None else None

    def _calibration_frame_size_px(self) -> tuple[int, int]:
        if self._record_video:
            return 1280, 720
        config = getattr(self._obj, "_config", None)
        if config is not None:
            parsed = self._parse_resolution(config.get("camera.resolution", ""))
            if parsed is not None:
                return parsed
        try:
            frame = self._camera.get_latest_frame()
            if frame is not None:
                h, w = frame.shape[:2]
                if w > 0 and h > 0:
                    return int(w), int(h)
        except Exception:
            pass
        return 1280, 720

    @staticmethod
    def _parse_resolution(value: object) -> tuple[int, int] | None:
        parts = str(value or "").lower().replace("×", "x").split("x", 1)
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

    def _stage_scale_um_per_step(self) -> tuple[float, float]:
        config = getattr(self._obj, "_config", None)
        if config is None:
            return 0.0, 0.0
        try:
            x = float(config.get("motor.stage_um_per_step_x", 0.0))
            y = float(config.get("motor.stage_um_per_step_y", 0.0))
            return x, y
        except Exception:
            return 0.0, 0.0

    def _move_rel_blocking(self, dx: int, dy: int, dz: int) -> bool:
        if hasattr(self._motion, "move_rel_blocking"):
            try:
                return bool(self._motion.move_rel_blocking(dx, dy, dz, source="automation"))
            except TypeError:
                return bool(self._motion.move_rel_blocking(dx, dy, dz))
        return bool(self._motion.move_rel(dx, dy, dz, source="automation"))

    def _requested_output_mode(self) -> str:
        return _OUTPUT_STITCH if self._stitch_after else _OUTPUT_MOSAIC

    def _render_scan_result(self, tiles: list[dict]) -> tuple[np.ndarray, str]:
        if self._stitch_after:
            stitched = self._try_stitch_tiles(tiles)
            if stitched is not None:
                return stitched, _OUTPUT_STITCH
        return self._grid_mosaic(tiles), _OUTPUT_MOSAIC

    def _stitch_tiles(self, tiles: list[dict]) -> np.ndarray:
        return self._render_scan_result(tiles)[0]

    def _try_stitch_tiles(self, tiles: list[dict]) -> np.ndarray | None:
        images = [tile["frame"] for tile in tiles if tile.get("frame") is not None]
        if len(images) < 2:
            return None

        try:
            import cv2

            self.stitch_progress.emit(0.1)
            bgr = [img[:, :, ::-1] for img in images]
            stitcher = cv2.Stitcher_create(cv2.Stitcher_SCANS)
            status, pano = stitcher.stitch(bgr)
            self.stitch_progress.emit(0.8)
            if status == cv2.Stitcher_OK and pano is not None:
                return pano[:, :, ::-1]
            print(f"[stitch] stitcher failed with status {status}. Using grid mosaic")
        except Exception as e:
            print(f"[stitch] failed: {e}. Using grid mosaic")
        return None

    def _grid_mosaic(self, tiles: list[dict]) -> np.ndarray:
        if not tiles:
            return np.zeros((1, 1, 3), dtype=np.uint8)
        sample = tiles[0]["frame"]
        tile_h, tile_w = sample.shape[:2]
        out = np.zeros((tile_h * self._rows, tile_w * self._cols, 3), dtype=np.uint8)
        for tile in tiles:
            col = int(tile.get("col", 0))
            row = int(tile.get("row", 0))
            frame = tile["frame"]
            y = row * tile_h
            x = col * tile_w
            out[y:y + tile_h, x:x + tile_w] = frame[:tile_h, :tile_w, :3]
        self.stitch_progress.emit(0.8)
        return out

    def _scan_metadata(
        self,
        stitched: np.ndarray,
        tile_count: int,
        requested_mode: str | None = None,
        actual_mode: str | None = None,
    ) -> dict:
        h, w = stitched.shape[:2]
        px, py, pz = self._get_position()
        requested = requested_mode or self._requested_output_mode()
        actual = actual_mode or requested
        metadata = {
            "version": 1,
            "type": "stitch",
            "captured_at": datetime.now().isoformat(timespec="seconds"),
            "objective": self._obj.active_objective,
            "position": {"x": px, "y": py, "z": pz},
            "width": int(w),
            "height": int(h),
            "resolution": {"width": int(w), "height": int(h)},
            "format": "OME-TIFF",
            "tiles": tile_count,
            "grid": {
                "columns": self._cols,
                "rows": self._rows,
                "overlap": self._overlap,
                "pattern": self._pattern,
            },
            "output": {
                "requested": requested,
                "actual": actual,
            },
            "tags": [],
        }
        return metadata

    def _position_dict(self) -> dict[str, int]:
        x, y, z = self._get_position()
        return {"x": int(x), "y": int(y), "z": int(z)}

    def _preflight_soft_limits(self, order: list[tuple[int, int]], step_x: int, step_y: int) -> bool:
        if not hasattr(self._motion, "can_move_to_xy"):
            return True
        try:
            start_x, start_y, _ = self._get_position()
        except Exception:
            return True
        for col, row in order:
            target_x = int(start_x) + col * step_x
            target_y = int(start_y) + row * step_y
            if not self._motion.can_move_to_xy(target_x, target_y, source="automation"):
                return False
        return True

    def _run_autofocus_and_wait(self) -> None:
        """Start autofocus and block until it finishes (or times out)."""
        if self._autofocus.busy:
            return

        done = threading.Event()

        def _on_finished():
            done.set()

        # One-shot connection
        self._autofocus.finished.connect(_on_finished)
        try:
            self._autofocus.start_autofocus()
            # Poll in short slices so a AF cancel is responsive
            deadline = time.monotonic() + _AF_TIMEOUT_S
            while not done.wait(timeout=0.2):
                if self._cancel or time.monotonic() >= deadline:
                    break
        finally:
            try:
                self._autofocus.finished.disconnect(_on_finished)
            except Exception:
                pass


class TileScannerService(QObject):
    """Manages the tile scanner worker lifecycle and exposes state."""

    busy_changed    = Signal(bool)
    paused_changed  = Signal(bool)
    progress        = Signal(float)
    tile_done       = Signal(int, int)
    finished        = Signal()
    stitch_started  = Signal()
    stitch_progress = Signal(float)
    stitch_finished = Signal(str)
    scan_saved      = Signal(str)

    def __init__(
        self,
        camera_svc,
        motion_ctrl,
        autofocus_svc,
        image_store,
        objective_mgr,
        get_position: Callable[[], tuple[int, int, int]] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._camera      = camera_svc
        self._motion      = motion_ctrl
        self._autofocus   = autofocus_svc
        self._image_store = image_store
        self._obj         = objective_mgr
        self._get_position = get_position
        self._worker: _TileScannerWorker | None = None
        self._busy   = False
        self._paused = False

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def paused(self) -> bool:
        return self._paused

    @Slot()
    def start(
        self,
        cols: int = 4,
        rows: int = 3,
        overlap: float = 0.2,
        pattern: str = "raster",
        autofocus_each: bool = False,
        record_video: bool = False,
        stitch_after: bool = False,
        settle_ms: int = 300,
    ) -> None:
        if self._busy:
            return
        self._paused = False

        self._worker = _TileScannerWorker(
            self._camera,
            self._motion,
            self._autofocus,
            self._image_store,
            self._obj,
            self._get_position,
            cols,
            rows,
            overlap,
            pattern,
            autofocus_each,
            record_video,
            session_dir=None,
            stitch_after=stitch_after,
            settle_ms=settle_ms,
        )
        self._worker.progress.connect(self.progress)
        self._worker.tile_done.connect(self.tile_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.stitch_started.connect(self.stitch_started)
        self._worker.stitch_progress.connect(self.stitch_progress)
        self._worker.stitch_finished.connect(self.stitch_finished)
        self._worker.scan_saved.connect(self.scan_saved)
        self._busy = True
        self.busy_changed.emit(True)
        self._worker.start()

    @Slot()
    def cancel(self) -> None:
        if self._worker and self._busy:
            self._worker.request_cancel()

    @Slot()
    def pause(self) -> None:
        if self._worker and self._busy and not self._paused:
            self._worker.request_pause()
            self._paused = True
            self.paused_changed.emit(True)

    @Slot()
    def resume(self) -> None:
        if self._worker and self._busy and self._paused:
            self._worker.request_resume()
            self._paused = False
            self.paused_changed.emit(False)

    def _on_finished(self) -> None:
        self._busy   = False
        self._paused = False
        self.busy_changed.emit(False)
        self.finished.emit()
        self._worker = None
