"""AutomationBridge: Exposes FocusStackerService and TileScannerService to QML."""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.domain import automation_plan
from retroscope.domain.scan_plan import tile_order

_MAX_COMPLETED = 20


class AutomationBridge(QObject):
    """Single bridge wrapping both automation services."""

    busy_changed          = Signal(bool)
    paused_changed        = Signal(bool)
    cancelling_changed    = Signal(bool)
    task_name_changed     = Signal(str)
    progress_changed      = Signal(float)
    frame_info_changed    = Signal()
    completed_changed     = Signal()

    def __init__(
        self,
        focus_stacker,
        tile_scanner,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fs  = focus_stacker
        self._ts  = tile_scanner

        # Runtime state
        self._busy        = False
        self._paused      = False
        self._cancelling  = False
        self._task_name   = ""
        self._task_progress = 0.0
        self._frame_cur   = 0
        self._frame_total = 0
        self._time_left   = ""
        self._completed: list[dict] = []
        self._stitch_pending   = False
        self._tile_record_video = False

        # ETA tracking
        self._task_start: float = 0.0
        self._steps_done: int   = 0
        self._steps_total: int  = 0

        # Wire focus stacker signals
        self._fs.paused_changed.connect(self._on_paused_changed)
        self._fs.frame_captured.connect(self._on_fs_frame_captured)
        self._fs.progress.connect(self._on_progress)
        self._fs.finished.connect(self._on_fs_finished)

        # Wire tile scanner signals
        self._ts.paused_changed.connect(self._on_paused_changed)
        self._ts.tile_done.connect(self._on_tile_done)
        self._ts.progress.connect(self._on_progress)
        self._ts.finished.connect(self._on_ts_finished)
        self._ts.stitch_started.connect(self._on_stitch_started)
        self._ts.stitch_progress.connect(self._on_stitch_progress)
        self._ts.stitch_finished.connect(self._on_stitch_finished)


    # Properties
    @Property(bool, notify=busy_changed)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=paused_changed)
    def paused(self) -> bool:
        return self._paused

    @Property(bool, notify=cancelling_changed)
    def cancelling(self) -> bool:
        return self._cancelling

    @Property(str, notify=task_name_changed)
    def taskName(self) -> str:
        return self._task_name

    @Property(float, notify=progress_changed)
    def taskProgress(self) -> float:
        return self._task_progress

    @Property(int, notify=frame_info_changed)
    def taskFrameCurrent(self) -> int:
        return self._frame_cur

    @Property(int, notify=frame_info_changed)
    def taskFrameTotal(self) -> int:
        return self._frame_total

    @Property(str, notify=frame_info_changed)
    def taskTimeLeft(self) -> str:
        return self._time_left

    @Property("QVariantList", notify=completed_changed)
    def completedTasks(self) -> list:
        return list(reversed(self._completed))

    @Slot(int, int, result=int)
    def focusStackTotalSteps(self, z_start: int, z_end: int) -> int:
        return automation_plan.focus_stack_total_steps(z_start, z_end)

    @Slot(int, int, int, result=int)
    def focusStackFrameCount(self, z_start: int, z_end: int, step_size: int) -> int:
        return automation_plan.focus_stack_frame_count(z_start, z_end, step_size)

    @Slot(int, int, int, result=int)
    def focusStackPreviewLines(self, z_start: int, z_end: int, step_size: int) -> int:
        return automation_plan.focus_stack_preview_lines(z_start, z_end, step_size)

    @Slot(int, int, int, int, result=int)
    def estimateFocusStackSeconds(
        self,
        z_start: int,
        z_end: int,
        step_size: int,
        settle_ms: int,
    ) -> int:
        return automation_plan.estimate_focus_stack_seconds(
            z_start,
            z_end,
            step_size,
            settle_ms,
        )

    @Slot(int, int, result=int)
    def tileCount(self, cols: int, rows: int) -> int:
        return automation_plan.tile_count(cols, rows)

    @Slot(int, int, int, result=int)
    def estimateTileScanSeconds(self, cols: int, rows: int, settle_ms: int) -> int:
        return automation_plan.estimate_tile_scan_seconds(cols, rows, settle_ms)

    @Slot(int, int, str, result="QVariantList")
    def tileOrder(self, cols: int, rows: int, pattern: str) -> list[dict[str, int]]:
        return [
            {"col": col, "row": row}
            for col, row in tile_order(cols, rows, pattern)
        ]

    # Slots
    @Slot(int, int, int, int, str)
    def startFocusStackAbsolute(
        self,
        z_start: int,
        z_end: int,
        step_size: int = 5,
        settle_ms: int = 150,
        blending: str = "laplacian",
    ) -> None:
        if self._busy:
            return
        total = abs(z_end - z_start)
        n_frames = automation_plan.focus_stack_frame_count(z_start, z_end, step_size)
        self._start_task("Focus stack", total_steps=n_frames)
        self._fs.start(
            z_half_range=total // 2,
            step_size=step_size,
            settle_ms=settle_ms,
            blending=blending,
            z_start_abs=z_start,
            z_end_abs=z_end,
        )

    @Slot(int, int, float, str, bool, bool, bool, int)
    def startTileScan(
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
        self._tile_record_video = record_video
        self._stitch_pending = stitch_after and not record_video
        self._start_task(f"Tile scan {cols}×{rows}", total_steps=automation_plan.tile_count(cols, rows))
        self._ts.start(cols, rows, overlap, pattern, autofocus_each, record_video, stitch_after, settle_ms)

    @Slot()
    def cancelTask(self) -> None:
        if not self._busy:
            return
        self._cancelling = True
        self.cancelling_changed.emit(True)
        if self._fs.busy:
            self._fs.cancel()
        elif self._ts.busy:
            self._ts.cancel()

    @Slot()
    def pauseTask(self) -> None:
        if self._fs.busy:
            self._fs.pause()
        elif self._ts.busy:
            self._ts.pause()

    @Slot()
    def resumeTask(self) -> None:
        if self._fs.busy:
            self._fs.resume()
        elif self._ts.busy:
            self._ts.resume()


    # Internal helpers
    def _start_task(self, name: str, total_steps: int) -> None:
        self._task_name    = name
        self._task_progress = 0.0
        self._frame_cur    = 0
        self._frame_total  = total_steps
        self._steps_done   = 0
        self._steps_total  = total_steps
        self._time_left    = ""
        self._task_start   = time.monotonic()
        self._busy         = True
        self._paused       = False
        self.busy_changed.emit(True)
        self.task_name_changed.emit(name)
        self.progress_changed.emit(0.0)
        self.frame_info_changed.emit()

    def _on_paused_changed(self, paused: bool) -> None:
        self._paused = paused
        self.paused_changed.emit(paused)

    def _on_fs_frame_captured(self, current: int, total: int) -> None:
        self._frame_cur   = current
        self._frame_total = total
        self._steps_done  = current
        self._steps_total = total
        self._update_eta()
        self.frame_info_changed.emit()

    def _on_tile_done(self, col: int, row: int) -> None:
        self._frame_cur  += 1
        self._steps_done  = self._frame_cur
        self._update_eta()
        self.frame_info_changed.emit()

    def _on_progress(self, value: float) -> None:
        self._task_progress = value
        self.progress_changed.emit(value)

    def _on_fs_finished(self, path: str) -> None:
        cancelled = (path == "")
        detail = f"{self._frame_total} frames"
        self._finish_task(cancelled, detail)

    def _on_ts_finished(self) -> None:
        if not self._busy:
            return
        if self._cancelling:
            # Cancelled scan skips saving and stitching
            self._stitch_pending = False
            self._finish_task(True, "cancelled")
            return
        if self._stitch_pending:
            return  # wait for stitch_finished
        detail = "video recorded" if self._tile_record_video else f"{self._frame_total} tiles"
        self._finish_task(False, detail)

    def _on_stitch_started(self) -> None:
        self._task_name = "Stitching…"
        self._task_progress = 0.0
        self.task_name_changed.emit(self._task_name)
        self.progress_changed.emit(0.0)

    def _on_stitch_progress(self, value: float) -> None:
        self._task_progress = value
        self.progress_changed.emit(value)

    def _on_stitch_finished(self, path: str) -> None:
        if not self._busy:
            return
        self._stitch_pending = False
        tiles = self._frame_total
        if path:
            detail = f"{tiles} tiles. Scan saved"
        else:
            detail = f"{tiles} tiles. Stitch failed"
        self._finish_task(path == "" and tiles == 0, detail)

    def _finish_task(self, cancelled: bool, detail: str) -> None:
        name = self._task_name
        if not cancelled:
            entry = {
                "name":   name,
                "time":   datetime.now().strftime("%H:%M"),
                "detail": detail,
            }
            self._completed.append(entry)
            if len(self._completed) > _MAX_COMPLETED:
                self._completed.pop(0)
            self.completed_changed.emit()

        self._busy          = False
        self._paused        = False
        self._cancelling    = False
        self._tile_record_video = False
        self._task_name     = ""
        self._task_progress = 0.0
        self._frame_cur     = 0
        self._frame_total   = 0
        self._time_left     = ""
        self.busy_changed.emit(False)
        self.paused_changed.emit(False)
        self.cancelling_changed.emit(False)
        self.task_name_changed.emit("")
        self.progress_changed.emit(0.0)
        self.frame_info_changed.emit()

    def _update_eta(self) -> None:
        if self._steps_done <= 0 or self._steps_total <= 0:
            self._time_left = ""
            return
        elapsed = time.monotonic() - self._task_start
        avg_per_step = elapsed / self._steps_done
        remaining = (self._steps_total - self._steps_done) * avg_per_step
        if remaining < 5:
            self._time_left = "< 5 s"
        elif remaining < 60:
            self._time_left = f"~{int(remaining)} s left"
        else:
            mins = int(remaining / 60)
            self._time_left = f"~{mins} min left"
