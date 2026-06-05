"""Contrast-based autofocus service. 

Performs a configurable coarse/fine Z sweep, samples focus scores from CameraService after each settled move, then commits to the best fine position when valid.

Note: Partially AI-generated (Parabolic peak interpolation)
"""

from __future__ import annotations

import logging
import threading
import time
from statistics import median
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.domain.focus_metrics import parabolic_peak

logger = logging.getLogger(__name__)

_DEFAULT_RANGE_MULTIPLIER = 10

# Hard limits, clamp config values 
_MIN_COARSE_POSITIONS = 7
_MAX_COARSE_POSITIONS = 41
_MIN_FINE_POSITIONS = 5
_MAX_FINE_POSITIONS = 41
_MIN_SETTLE_MS = 50
_MAX_SETTLE_MS = 2000
_MIN_MOVE_START_MS = 100
_MAX_MOVE_START_MS = 3000
_MIN_SAMPLES_PER_POSITION = 1
_MAX_SAMPLES_PER_POSITION = 5
_MIN_CONFIDENCE_FLOOR = 0.0
_MIN_CONFIDENCE_CEIL = 5000.0


def _profile_autofocus_range(profile) -> int:
    configured = int(getattr(profile, "autofocus_range_steps", 0) or 0)
    if configured > 0:
        return configured
    dof = int(getattr(profile, "dof_steps", 1) or 1)
    stack = int(getattr(profile, "focus_stack_step", 1) or 1)
    return max(200, dof * _DEFAULT_RANGE_MULTIPLIER, stack * 40)


def _odd_count(value: Any, lo: int, hi: int, default: int) -> int:
    count = _clamp_int(value, lo, hi, default)
    if count % 2 == 0:
        count = min(hi, count + 1)
    return count


def centered_sweep_offsets(step: int, count: int) -> list[int]:
    """Return sampled offsets: centre, upward half, then downward half."""
    count = max(1, int(count))
    if count % 2 == 0:
        count += 1
    half = count // 2
    return [0] + [step * i for i in range(1, half + 1)] + [-step * i for i in range(1, half + 1)]


def autofocus_sample_positions(profile, coarse_positions: int = 21) -> list[int]:
    """Return sampled coarse offsets: centre, upward half, then downward half."""
    coarse_positions = _odd_count(coarse_positions, _MIN_COARSE_POSITIONS, _MAX_COARSE_POSITIONS, 21)
    search_range = _profile_autofocus_range(profile)
    half = coarse_positions // 2
    step = max(5, int(round(search_range / max(1, half))))
    return centered_sweep_offsets(step, coarse_positions)


def _clamp_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _clamp_float(value: Any, lo: float, hi: float, default: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


class _AutofocusWorker(QThread):
    """Background thread that executes the coarse + fine Z sweep."""

    progress = Signal(float)      # 0.0–1.0
    failed   = Signal(str)        
    finished = Signal()

    def __init__(self, camera_svc, motion_ctrl, objective_mgr, config, parent=None):
        super().__init__(parent)
        self._camera = camera_svc
        self._motion = motion_ctrl
        self._obj    = objective_mgr
        self._config = config
        self._cancel = False
        self._cancel_event = threading.Event()
        # Defaults (overwritten from config)
        self._settle_s            = 0.30
        self._move_start_s        = 0.80
        self._coarse_positions    = 21
        self._fine_positions      = 21
        self._samples_per_position = 2
        self._min_confidence      = 50.0
        self._analysis_fps        = 8

    def request_cancel(self) -> None:
        self._cancel = True
        self._cancel_event.set()

    def _sleep_cancelable(self, delay_s: float) -> bool:
        if delay_s <= 0.0:
            return not self._cancel
        return not self._cancel_event.wait(delay_s)

    # Config (read at the start of every run)
    def _load_config(self) -> None:
        cfg = self._config
        get = cfg.get if cfg is not None else (lambda *_a, **_k: None)
        self._settle_s = _clamp_int(
            get("autofocus.settle_ms", 300), _MIN_SETTLE_MS, _MAX_SETTLE_MS, 300
        ) / 1000.0
        self._move_start_s = _clamp_int(
            get("autofocus.move_start_ms", 800), _MIN_MOVE_START_MS, _MAX_MOVE_START_MS, 800
        ) / 1000.0
        self._coarse_positions = _odd_count(
            get("autofocus.coarse_positions", 21),
            _MIN_COARSE_POSITIONS, _MAX_COARSE_POSITIONS, 21,
        )
        self._fine_positions = _odd_count(
            get("autofocus.fine_positions", 21), _MIN_FINE_POSITIONS, _MAX_FINE_POSITIONS, 21
        )
        self._samples_per_position = _clamp_int(
            get("autofocus.samples_per_position", 2),
            _MIN_SAMPLES_PER_POSITION, _MAX_SAMPLES_PER_POSITION, 2,
        )
        self._min_confidence = _clamp_float(
            get("autofocus.min_confidence", 50.0),
            _MIN_CONFIDENCE_FLOOR, _MIN_CONFIDENCE_CEIL, 50.0,
        )
        self._analysis_fps = _clamp_int(get("camera.fps", 8), 1, 30, 8)

    # Per-position score
    def _focus_score_timeout_s(self) -> float:
        frame_period_s = 1.0 / max(1, self._analysis_fps)
        return min(2.5, max(0.35, self._settle_s + 0.3, frame_period_s * 2.5))

    def _raw_focus_sequence(self) -> int:
        if hasattr(self._camera, "raw_focus_sequence"):
            return int(self._camera.raw_focus_sequence())
        return 0

    def _grab_score(self) -> float | None:
        """Median of live focus scores. The sequence is captured after the motor settle delay."""

        if not hasattr(self._camera, "wait_for_next_raw_focus_score"):
            logger.info("[autofocus] camera service has no raw focus-score stream")
            return None

        timeout = self._focus_score_timeout_s()
        sample_started = time.monotonic()
        after_sequence = self._raw_focus_sequence()
        scores: list[float] = []
        for _ in range(self._samples_per_position):
            deadline = time.monotonic() + timeout
            score = None
            while not self._cancel:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                waited_for = min(0.05, remaining)
                wait_started = time.monotonic()
                score = self._camera.wait_for_next_raw_focus_score(
                    after_sequence=after_sequence,
                    timeout=waited_for,
                )
                if score is not None:
                    break
                latest = self._latest_score_from_current_settle(sample_started)
                if latest is not None:
                    score = latest
                    break
                if time.monotonic() - wait_started < waited_for * 0.5:
                    self._cancel_event.wait(min(0.01, max(0.0, remaining)))
            if score is None:
                break
            scores.append(float(score))
            after_sequence = self._raw_focus_sequence()
        if not scores:
            latest = self._latest_score_from_current_settle(sample_started)
            if latest is not None:
                scores.append(latest)
            else:
                logger.info("[autofocus] no fresh focus score within %.2fs", timeout)
                return None

        if hasattr(self._camera, "raw_focus_status"):
            seq, latest, age, source = self._camera.raw_focus_status()
            age_label = "n/a" if age is None else f"{age:.3f}s"
            latest_label = "n/a" if latest is None else f"{latest:.1f}"
            logger.debug(
                "[autofocus] sampled %d raw focus score(s), source=%s seq=%d age=%s latest=%s median=%.1f",
                len(scores),
                source or "unknown",
                seq,
                age_label,
                latest_label,
                median(scores),
            )
        return float(median(scores))

    def _latest_score_from_current_settle(self, sample_started: float) -> float | None:
        if not hasattr(self._camera, "raw_focus_status"):
            return None
        try:
            _seq, latest, age, source = self._camera.raw_focus_status()
        except Exception:
            return None
        if latest is None or age is None:
            return None
        latest_t = time.monotonic() - float(age)
        settle_window_s = max(0.05, min(0.5, self._settle_s))
        if latest_t < sample_started - settle_window_s:
            return None
        logger.debug(
            "[autofocus] using latest raw focus score from current settle window, source=%s age=%.3fs latest=%.1f",
            source or "unknown",
            float(age),
            float(latest),
        )
        return float(latest)

    # Main routine
    def run(self) -> None:
        self._load_config()
        profile = self._obj.current_profile()
        fss = profile.focus_stack_step   # per-objective step

        coarse_offsets = autofocus_sample_positions(profile, self._coarse_positions)
        fine_step = max(fss * 2, 5)
        fine_offsets = centered_sweep_offsets(fine_step, self._fine_positions)
        # +2: move to best coarse base, then to best fine position
        total_steps = len(coarse_offsets) + len(fine_offsets) + 2
        done = 0

        def emit_progress(extra: int = 0) -> None:
            self.progress.emit(min(1.0, (done + extra) / total_steps))

        rel_pos = 0
        failed_emitted = False

        def move_and_wait(delta: int, delay_s: float) -> bool:
            nonlocal rel_pos
            if self._cancel:
                return False
            if delta == 0:
                return True
            try:
                if hasattr(self._motion, "move_z_blocking"):
                    ok = self._motion.move_z_blocking(delta)
                else:
                    ok = self._motion.move_z(delta)
            except Exception:
                logger.exception("[autofocus] move_z failed")
                return False
            if ok is False:
                return False
            rel_pos += int(delta)
            return self._sleep_cancelable(delay_s)

        def finish_cancelled() -> None:
            nonlocal failed_emitted
            failed_emitted = True
            self.failed.emit("Cancelled")
            self.finished.emit()

        def return_to_start_and_fail(reason: str) -> None:
            nonlocal failed_emitted
            failed_emitted = True
            try:
                move_and_wait(-rel_pos, self._move_start_s)
            except Exception:
                logger.exception("[autofocus] return-to-start move failed")
            self.failed.emit(reason)
            self.finished.emit()

        def sample_current() -> float | None:
            score = self._grab_score()
            if score is None:
                return None
            return score

        def run_centered_sweep(center_rel: int, offsets: list[int]) -> list[tuple[int, float]] | None:
            nonlocal done
            if not move_and_wait(center_rel - rel_pos, self._move_start_s):
                if self._cancel:
                    finish_cancelled()
                return None

            scores: list[tuple[int, float]] = []
            for index, offset in enumerate(offsets):
                if self._cancel:
                    finish_cancelled()
                    return None

                target_rel = center_rel + offset
                if index == 0:
                    delay_s = self._move_start_s
                else:
                    previous_offset = offsets[index - 1]
                    returning_to_center = offset < 0 and previous_offset > 0
                    if returning_to_center and not move_and_wait(center_rel - rel_pos, self._move_start_s):
                        if self._cancel:
                            finish_cancelled()
                        return None
                    delay_s = self._settle_s

                if not move_and_wait(target_rel - rel_pos, delay_s):
                    if self._cancel:
                        finish_cancelled()
                    return None

                score = sample_current()
                if score is None:
                    if self._cancel:
                        finish_cancelled()
                        return None
                    return_to_start_and_fail("No fresh focus score")
                    return None
                scores.append((rel_pos, score))
                done += 1
                emit_progress()
            return scores

        # Coarse sweep
        coarse_scores = run_centered_sweep(0, coarse_offsets)
        if coarse_scores is None:
            if self._cancel or failed_emitted:
                return
            return_to_start_and_fail("Move failed")
            return

        best_coarse_rel = max(coarse_scores, key=lambda x: x[1])[0] if coarse_scores else 0
        best_coarse_score = max((s for _, s in coarse_scores), default=0.0)
        logger.debug(
            "[autofocus] coarse peak rel=%d score=%.1f over %d samples",
            best_coarse_rel, best_coarse_score, len(coarse_offsets),
        )

        if not move_and_wait(best_coarse_rel - rel_pos, self._move_start_s):
            return_to_start_and_fail("Move failed")
            return
        done += 1
        emit_progress()

        # Fine sweep
        fine_scores = run_centered_sweep(best_coarse_rel, fine_offsets)
        if fine_scores is None:
            if self._cancel or failed_emitted:
                return
            return_to_start_and_fail("Move failed")
            return

        # Min-confidence guard
        if not fine_scores:
            return_to_start_and_fail("No focus samples collected")
            return

        best_fine_score = max(s for _, s in fine_scores)
        if best_fine_score < self._min_confidence:
            reason = (
                f"best score {best_fine_score:.1f} below threshold {self._min_confidence:.1f}"
            )
            logger.info("[autofocus] %s. Aborting.", reason)
            return_to_start_and_fail(reason)
            return

        # Parabolic peak interpolation
        sorted_fine = sorted(fine_scores, key=lambda item: item[0])
        i_best = max(range(len(sorted_fine)), key=lambda j: sorted_fine[j][1])
        if 0 < i_best < len(sorted_fine) - 1:
            z_left,  s_left  = sorted_fine[i_best - 1]
            z_mid,   s_mid   = sorted_fine[i_best]
            z_right, s_right = sorted_fine[i_best + 1]
            target = parabolic_peak(z_left, s_left, z_mid, s_mid, z_right, s_right)
        else:
            target = sorted_fine[i_best][0]

        logger.debug(
            "[autofocus] fine peak rel=%d (parabolic) score=%.1f over %d samples",
            target, best_fine_score, len(fine_offsets),
        )

        # Commit move, final progress
        if not move_and_wait(target - rel_pos, self._move_start_s):
            return_to_start_and_fail("Move failed")
            return
        done += 1
        self.progress.emit(1.0)
        self.finished.emit()


class AutofocusService(QObject):
    """Manages the autofocus worker lifecycle and exposes state to the bridge."""

    busy_changed = Signal(bool)
    cancelling_changed = Signal(bool)
    progress     = Signal(float)   # 0.0–1.0
    failed       = Signal(str)     
    finished     = Signal()

    def __init__(self, camera_svc, motion_ctrl, objective_mgr, config,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._camera = camera_svc
        self._motion = motion_ctrl
        self._obj    = objective_mgr
        self._config = config
        self._worker: _AutofocusWorker | None = None
        self._busy = False
        self._cancelling = False

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def cancelling(self) -> bool:
        return self._cancelling

    @Slot()
    def start_autofocus(self) -> None:
        if self._busy:
            return
        self._worker = _AutofocusWorker(
            self._camera, self._motion, self._obj, self._config
        )
        self._worker.progress.connect(self.progress)
        self._worker.failed.connect(self.failed)
        self._worker.finished.connect(self._on_finished)
        self._busy = True
        self._cancelling = False
        self.busy_changed.emit(True)
        self.cancelling_changed.emit(False)
        self._worker.start()

    @Slot()
    def cancel(self) -> None:
        if self._worker and self._busy:
            if not self._cancelling:
                self._cancelling = True
                self.cancelling_changed.emit(True)
            self._worker.request_cancel()

    @Slot()
    def toggle(self) -> None:
        """Cancel a running routine, otherwise start one (UI + GPIO toggle AF)"""
        if self._busy:
            self.cancel()
        else:
            self.start_autofocus()

    def _on_finished(self) -> None:
        self._busy = False
        self._cancelling = False
        self.busy_changed.emit(False)
        self.cancelling_changed.emit(False)
        self.finished.emit()
        self._worker = None
