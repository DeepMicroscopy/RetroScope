"""Motion controller: Translates joystick/encoder input into Sangaboard moves.

Applies joystick dead-zone, exponential curve and objective speed limits.
Guards against endstop to prevent focus motor crashing into stage.

Note: Partially AI-generated (_dispatch_joystick_at, )
"""

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QObject, Property, QTimer, Signal, Slot

from retroscope.services.objective_manager import ObjectiveManager

DEADZONE = 0.05                     # inner dead-zone
ADC_MAX = 32767                     # ADS1115 full-scale positive value
ADC_UNIPOLAR_MAX_3V3 = 26400.0      # ADS volt range with a 3.3V joystick input
ENCODER_TRIGGER_UNITS = 50          # only move when this many encoder steps accumulated

_CALIBRATION_Z_ENCODER_STEP = 50    # Fixed Z motor steps per encoder trigger while a DoF calibration is active.
_STAGE_UM_PER_STEP_FALLBACK = 1.0   # used when stage hasn't been alibrate yet
_CALIBRATION_SAMPLES = 30
_BLOCK_REPEAT_S = 0.8
_AXIS_MIN_SPAN = 2048.0
_AXIS_INITIAL_SPAN = 8192.0
_JOYSTICK_PAN_COMMAND_BOOST = 10.0
_JOYSTICK_RELEASE_FACTOR = 0.70
_JOYSTICK_MAX_DISPATCH_DT_S = 0.25
_JOYSTICK_SAMPLE_TIMEOUT_S = 0.15


@dataclass(frozen=True)
class JoystickDispatchParams:
    interval_ms: int
    min_command_steps: int
    force_command_ms: int
    target_alpha: float

    @property
    def interval_s(self) -> float:
        return self.interval_ms / 1000.0

    @property
    def force_command_s(self) -> float:
        return self.force_command_ms / 1000.0


def joystick_dispatch_params() -> JoystickDispatchParams:
    """Return fixed low-latency joystick dispatch parameters."""
    return JoystickDispatchParams(
        interval_ms=25,
        min_command_steps=1,
        force_command_ms=50,
        target_alpha=0.90,
    )


class JoystickAxisNormalizer:
    """Normalizes one joystick axis using per-side spans."""

    def __init__(self) -> None:
        self._center: float | None = None
        self._low_span = _AXIS_MIN_SPAN
        self._high_span = _AXIS_MIN_SPAN

    def set_center(self, center: float | None) -> None:
        self._center = None if center is None else float(center)
        if self._center is None:
            self._low_span = _AXIS_MIN_SPAN
            self._high_span = _AXIS_MIN_SPAN
        else:
            self._low_span = _AXIS_INITIAL_SPAN
            self._high_span = _AXIS_INITIAL_SPAN

    def normalize(self, raw: float) -> float:
        if self._center is None:
            return 0.0
        raw = max(-float(ADC_MAX), min(float(ADC_MAX), float(raw)))
        delta = raw - self._center

        if delta >= 0.0:
            if delta > self._high_span:
                self._high_span = delta
            span = self._high_span
        else:
            low_delta = -delta
            if low_delta > self._low_span:
                self._low_span = low_delta
            span = self._low_span
        return max(-1.0, min(1.0, delta / span))

    @property
    def center(self) -> float | None:
        return self._center


def _joystick_curve(
    value: float,
    deadzone: float = DEADZONE,
    curve: str = "exponential",
    expo_strength: int = 70,
) -> float:
    """Apply dead-zone and selected response curve to a normalized axis value."""
    v = max(-1.0, min(1.0, value))
    sign = 1.0 if v >= 0 else -1.0
    abs_v = abs(v)
    if abs_v < deadzone:
        return 0.0
    normed = (abs_v - deadzone) / (1.0 - deadzone)
    if curve == "linear":
        shaped = normed
    elif curve == "scurve":
        shaped = normed * normed * (3.0 - 2.0 * normed)
    else:
        expo = max(0, min(100, int(expo_strength))) / 100.0
        shaped = normed ** (1.0 + expo * 2.0)
    return sign * shaped


class MotionController(QObject):
    """Receives normalized inputs and issues Sangaboard commands."""

    motion_blocked          = Signal(str)   # "endstop", "soft_limit_stage", etc.
    joystick_cal_done       = Signal()
    joystick_center_changed = Signal()
    deadzone_changed        = Signal()
    soft_limits_changed     = Signal()
    position_reset          = Signal(int, int, int)
    stage_zeroed            = Signal()
    backlash_slack_changed  = Signal(float, float, float)

    def __init__(self, sangaboard, objective_manager: ObjectiveManager,
                 config=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sb = sangaboard
        self._obj = objective_manager
        self._config = config
        self._endstop = False
        self._pos_x = 0
        self._pos_y = 0
        self._pos_z = 0
        self._expected_x = 0
        self._expected_y = 0
        self._expected_z = 0
        self._encoder_accum = 0
        self._encoder_sensitivity_pct = 100
        self._calibration_encoder_step_active = False
        self._deadzone: float = DEADZONE
        self._joystick_curve_name = str(config.get("input.curve", "exponential") if config is not None else "exponential")
        if self._joystick_curve_name not in {"linear", "exponential", "scurve"}:
            self._joystick_curve_name = "exponential"
        self._joystick_expo_strength = int(config.get("input.expo_strength", 70) if config is not None else 70)
        self._joystick_sensitivity_pct = max(
            10,
            min(300, int(config.get("input.sensitivity_pct", 100) if config is not None else 100)),
        )
        self._joystick_dispatch = joystick_dispatch_params()
        self._max_pan_speed_px_per_sec = max(
            10,
            min(4000, int(config.get("input.max_pan_speed_px_per_sec", 400) if config is not None else 400)),
        )
        self._z_encoder_step_multiplier = max(
            0.25,
            min(4.0, float(config.get("input.z_encoder_step_multiplier", 1.0) if config is not None else 1.0)),
        )
        self._center_x: float | None = None
        self._center_y: float | None = None
        self._calibration_samples = 0
        self._calibration_sum_x = 0.0
        self._calibration_sum_y = 0.0
        self._swap_xy = False
        self._invert_x = False
        self._invert_y = False
        self._axis_norm_x = JoystickAxisNormalizer()
        self._axis_norm_y = JoystickAxisNormalizer()
        self._joystick_sample_ready = False
        self._joystick_x_raw = 0
        self._joystick_y_raw = 0
        self._joystick_x_axis = 0
        self._joystick_y_axis = 0
        self._joystick_norm_x = 0.0
        self._joystick_norm_y = 0.0
        self._joystick_sample_t = 0.0
        self._joystick_x_active = False
        self._joystick_y_active = False
        self._joystick_x_sign = 0
        self._joystick_y_sign = 0
        self._vx_filtered = 0.0
        self._vy_filtered = 0.0
        self._dx_accum = 0.0
        self._dy_accum = 0.0
        self._last_joystick_dispatch_t = 0.0
        self._joystick_pending_since_t: float | None = None
        self._joystick_timer = QTimer(self)
        self._joystick_timer.setInterval(self._joystick_dispatch.interval_ms)
        self._joystick_timer.timeout.connect(self._dispatch_joystick)
        if QCoreApplication.instance() is not None:
            self._joystick_timer.start()
        # Backlash hysteresis-band slack state per axis.
        self._slack_x: float = 0.0
        self._slack_y: float = 0.0
        self._slack_z: float = 0.0
        self._last_block_reason = ""
        self._last_block_t = 0.0
        self._soft_enabled = False
        self._soft_calibrated = False
        self._soft_x_min = 0
        self._soft_x_max = 0
        self._soft_y_min = 0
        self._soft_y_max = 0
        self._load_soft_limits()

    @staticmethod
    def _take_whole_steps(value: float) -> tuple[int, float]:
        if value >= 0:
            whole = int(math.floor(value))
        else:
            whole = int(math.ceil(value))
        return whole, value - whole

    @staticmethod
    def _sign(value: float) -> int:
        return 1 if value > 0.0 else -1 if value < 0.0 else 0

    @staticmethod
    def _plan_axis(
        delta: int,
        slack: float,
        backlash: int,
        apply_backlash: bool,
    ) -> tuple[int, float]:
        """Computes the motor-step delta for an axis while tracking backlash slack, optionally adding compensation so we reach the requested position exactly."""

        if delta == 0 or backlash <= 0:
            return int(delta), float(slack)
        half = backlash / 2.0
        sign = 1 if delta > 0 else -1
        if apply_backlash:
            pre = sign * half - slack
            motor_delta = int(round(delta + pre))
            new_slack = sign * half
        else:
            motor_delta = int(delta)
            new_slack = max(-half, min(half, slack + delta))
        return motor_delta, new_slack

    def backlash_slack_state(self) -> tuple[float, float, float]:
        """Return the current per-axis backlash slack estimate."""
        return (self._slack_x, self._slack_y, self._slack_z)

    def _emit_backlash_slack_changed(self) -> None:
        self.backlash_slack_changed.emit(self._slack_x, self._slack_y, self._slack_z)

    def _commit_backlash_slack(
        self,
        dx: int,
        dy: int,
        dz: int,
        new_slack: tuple[float, float, float],
    ) -> None:
        old_slack = self.backlash_slack_state()
        slack_x, slack_y, slack_z = old_slack
        new_slack_x, new_slack_y, new_slack_z = new_slack
        if dx != 0:
            slack_x = new_slack_x
        if dy != 0:
            slack_y = new_slack_y
        if dz != 0:
            slack_z = new_slack_z
        if (slack_x, slack_y, slack_z) == old_slack:
            return
        self._slack_x = slack_x
        self._slack_y = slack_y
        self._slack_z = slack_z
        self._emit_backlash_slack_changed()

    def _refresh_motion_settings_from_config(self) -> None:
        if self._config is None:
            return
        self._max_pan_speed_px_per_sec = max(
            10,
            min(4000, int(self._config.get("input.max_pan_speed_px_per_sec", self._max_pan_speed_px_per_sec))),
        )

    def _clear_joystick_motion_state(self, *, clear_sample: bool = False) -> None:
        self._joystick_x_active = False
        self._joystick_y_active = False
        self._joystick_x_sign = 0
        self._joystick_y_sign = 0
        self._vx_filtered = 0.0
        self._vy_filtered = 0.0
        self._dx_accum = 0.0
        self._dy_accum = 0.0
        self._joystick_pending_since_t = None
        if clear_sample:
            self._joystick_sample_ready = False
            self._joystick_norm_x = 0.0
            self._joystick_norm_y = 0.0

    # Position and soft-limit state
    @Slot(int, int, int)
    def on_position_updated(self, x: int, y: int, z: int) -> None:
        self._pos_x, self._pos_y, self._pos_z = int(x), int(y), int(z)
        self._expected_x, self._expected_y, self._expected_z = self._pos_x, self._pos_y, self._pos_z

    @property
    def soft_limits_enabled(self) -> bool:
        return self._soft_enabled

    @property
    def soft_limits_calibrated(self) -> bool:
        return self._soft_calibrated

    @property
    def soft_limit_x_min(self) -> int:
        return self._soft_x_min

    @property
    def soft_limit_x_max(self) -> int:
        return self._soft_x_max

    @property
    def soft_limit_y_min(self) -> int:
        return self._soft_y_min

    @property
    def soft_limit_y_max(self) -> int:
        return self._soft_y_max

    @Slot(result=bool)
    def confirm_home_zero(self) -> bool:
        """Set the current firmware position to 0,0,0 after Z is homed."""
        if not self._endstop:
            self._emit_motion_blocked("stage_home_requires_endstop")
            return False
        if not hasattr(self._sb, "zero_position"):
            self._emit_motion_blocked("stage_home_failed")
            return False
        try:
            self._sb.zero_position()
        except Exception:
            self._emit_motion_blocked("stage_home_failed")
            return False

        self._pos_x = self._pos_y = self._pos_z = 0
        self._expected_x = self._expected_y = self._expected_z = 0
        self._clear_joystick_motion_state(clear_sample=True)
        self.invalidate_backlash_history()
        self._soft_enabled = False
        self._soft_calibrated = False
        self._soft_x_min = self._soft_x_max = 0
        self._soft_y_min = self._soft_y_max = 0
        self._save_soft_limits()
        self.soft_limits_changed.emit()
        self.position_reset.emit(0, 0, 0)
        self.stage_zeroed.emit()
        return True

    @Slot(result=bool)
    def save_bottom_right_limit(self) -> bool:
        """Capture the current XY position as the opposite soft-limit corner."""
        x = int(self._pos_x)
        y = int(self._pos_y)
        if x == 0 or y == 0:
            self._emit_motion_blocked("soft_limits_invalid")
            return False

        self._soft_x_min = min(0, x)
        self._soft_x_max = max(0, x)
        self._soft_y_min = min(0, y)
        self._soft_y_max = max(0, y)
        self._soft_calibrated = True
        self._soft_enabled = True
        self._save_soft_limits()
        self.soft_limits_changed.emit()
        return True

    @Slot(bool, result=bool)
    def set_soft_limits_enabled(self, enabled: bool) -> bool:
        if enabled and not self._soft_calibrated:
            self._emit_motion_blocked("soft_limits_uncalibrated")
            return False
        if self._soft_enabled == bool(enabled):
            return True
        self._soft_enabled = bool(enabled)
        self._save_soft_limits()
        self.soft_limits_changed.emit()
        return True

    @Slot()
    def clear_soft_limits(self) -> None:
        self._soft_enabled = False
        self._soft_calibrated = False
        self._soft_x_min = self._soft_x_max = 0
        self._soft_y_min = self._soft_y_max = 0
        self._save_soft_limits()
        self.soft_limits_changed.emit()

    def can_move_to_xy(self, x: int, y: int, source: str = "manual", emit_block: bool = True) -> bool:
        if not self._soft_limits_active():
            return True
        inside = (
            self._soft_x_min <= int(x) <= self._soft_x_max
            and self._soft_y_min <= int(y) <= self._soft_y_max
        )
        if not inside and emit_block:
            self._emit_motion_blocked(self._soft_limit_reason(source))
        return inside

    def _load_soft_limits(self) -> None:
        if self._config is None:
            return
        self._soft_enabled = bool(self._config.get("motor.soft_limits.enabled", False))
        self._soft_calibrated = bool(self._config.get("motor.soft_limits.calibrated", False))
        self._soft_x_min = int(self._config.get("motor.soft_limits.x_min", 0))
        self._soft_x_max = int(self._config.get("motor.soft_limits.x_max", 0))
        self._soft_y_min = int(self._config.get("motor.soft_limits.y_min", 0))
        self._soft_y_max = int(self._config.get("motor.soft_limits.y_max", 0))
        self._normalize_soft_limits()
        if not self._soft_calibrated:
            self._soft_enabled = False

    def _save_soft_limits(self) -> None:
        self._normalize_soft_limits()
        if self._config is None:
            return
        self._config.set("motor.soft_limits.enabled", self._soft_enabled)
        self._config.set("motor.soft_limits.calibrated", self._soft_calibrated)
        self._config.set("motor.soft_limits.x_min", self._soft_x_min)
        self._config.set("motor.soft_limits.x_max", self._soft_x_max)
        self._config.set("motor.soft_limits.y_min", self._soft_y_min)
        self._config.set("motor.soft_limits.y_max", self._soft_y_max)
        if hasattr(self._config, "save"):
            self._config.save()

    def _normalize_soft_limits(self) -> None:
        self._soft_x_min, self._soft_x_max = sorted((int(self._soft_x_min), int(self._soft_x_max)))
        self._soft_y_min, self._soft_y_max = sorted((int(self._soft_y_min), int(self._soft_y_max)))

    def _soft_limits_active(self) -> bool:
        return self._soft_enabled and self._soft_calibrated

    def _soft_limit_reason(self, source: str) -> str:
        return "soft_limit_automation" if source == "automation" else "soft_limit_stage"

    def _emit_motion_blocked(self, reason: str) -> None:
        now = time.monotonic()
        if reason == self._last_block_reason and now - self._last_block_t < _BLOCK_REPEAT_S:
            return
        self._last_block_reason = reason
        self._last_block_t = now
        self.motion_blocked.emit(reason)

    def _planned_moves(
        self,
        dx: int,
        dy: int,
        dz: int,
        *,
        apply_backlash: bool,
    ) -> tuple[list[tuple[int, int, int]], tuple[float, float, float]]:
        """Plans the combined motor-step command for a requested move and returns the updated backlash slack state (or no command if no movement is needed)."""

        profile = self._obj.current_profile()
        backlash_x = int(getattr(profile, "backlash_x", 0))
        backlash_y = int(getattr(profile, "backlash_y", 0))
        backlash_z = int(getattr(profile, "backlash_z", 0))

        mx, new_slack_x = self._plan_axis(int(dx), self._slack_x, backlash_x, apply_backlash)
        my, new_slack_y = self._plan_axis(int(dy), self._slack_y, backlash_y, apply_backlash)
        mz, new_slack_z = self._plan_axis(int(dz), self._slack_z, backlash_z, apply_backlash)

        moves: list[tuple[int, int, int]] = []
        if mx != 0 or my != 0 or mz != 0:
            moves.append((mx, my, mz))

        return moves, (new_slack_x, new_slack_y, new_slack_z)

    def preview_move_rel(
        self,
        dx: int,
        dy: int,
        dz: int,
        *,
        apply_backlash: bool = True,
    ) -> dict[str, object]:
        """Preview the motor command for a relative move without side effects."""
        slack_before = (self._slack_x, self._slack_y, self._slack_z)
        moves, slack_after = self._planned_moves(
            int(dx),
            int(dy),
            int(dz),
            apply_backlash=apply_backlash,
        )
        motor_dx = sum(move[0] for move in moves)
        motor_dy = sum(move[1] for move in moves)
        motor_dz = sum(move[2] for move in moves)
        return {
            "requested_dx": int(dx),
            "requested_dy": int(dy),
            "requested_dz": int(dz),
            "motor_dx": int(motor_dx),
            "motor_dy": int(motor_dy),
            "motor_dz": int(motor_dz),
            "extra_x": int(motor_dx - int(dx)),
            "extra_y": int(motor_dy - int(dy)),
            "extra_z": int(motor_dz - int(dz)),
            "moves": list(moves),
            "slack_before": slack_before,
            "slack_after": slack_after,
        }

    def _move_rel_checked(
        self,
        dx: int,
        dy: int,
        dz: int,
        *,
        source: str = "manual",
        apply_backlash: bool = True,
        coalesce: bool = False,
    ) -> bool:
        moves, new_slack = self._planned_moves(int(dx), int(dy), int(dz), apply_backlash=apply_backlash)
        tx, ty = self._expected_x, self._expected_y
        for mx, my, mz in moves:
            if self._endstop and mz < 0:
                self._emit_motion_blocked("endstop")
                return False
            tx += mx
            ty += my
            if not self.can_move_to_xy(tx, ty, source=source):
                return False

        for mx, my, mz in moves:
            self._sb.move_rel(mx, my, mz, coalesce=coalesce)
            self._expected_x += mx
            self._expected_y += my
            self._expected_z += mz

        self._commit_backlash_slack(dx, dy, dz, new_slack)
        return True

    def _blocking_move_timeout_s(self, dx: int, dy: int, dz: int) -> float:
        distance = max(abs(int(dx)), abs(int(dy)), abs(int(dz)))
        return max(5.0, min(120.0, 2.0 + distance * 0.02))

    def _move_rel_checked_blocking(
        self,
        dx: int,
        dy: int,
        dz: int,
        *,
        source: str = "manual",
        apply_backlash: bool = True,
    ) -> bool:
        moves, new_slack = self._planned_moves(int(dx), int(dy), int(dz), apply_backlash=apply_backlash)
        tx, ty = self._expected_x, self._expected_y
        for mx, my, mz in moves:
            if self._endstop and mz < 0:
                self._emit_motion_blocked("endstop")
                return False
            tx += mx
            ty += my
            if not self.can_move_to_xy(tx, ty, source=source):
                return False

        if not hasattr(self._sb, "move_rel_blocking"):
            return self._move_rel_checked(dx, dy, dz, source=source, apply_backlash=apply_backlash)

        for mx, my, mz in moves:
            ok = self._sb.move_rel_blocking(
                mx,
                my,
                mz,
                timeout=self._blocking_move_timeout_s(mx, my, mz),
            )
            if not ok:
                self._emit_motion_blocked("stage_move_timeout")
                return False
            self._expected_x += mx
            self._expected_y += my
            self._expected_z += mz

        self._commit_backlash_slack(dx, dy, dz, new_slack)
        return True

    # Slots called from InputManager
    @Slot(int, int)
    def on_axes_updated(self, x_raw: int, y_raw: int) -> None:
        """Receive raw ADC values and update the latest joystick intent."""
        x_axis, y_axis = self._map_joystick_raw_axes(x_raw, y_raw)
        if self._center_x is None or self._center_y is None:
            self._calibration_sum_x += x_axis
            self._calibration_sum_y += y_axis
            self._calibration_samples += 1
            if self._calibration_samples >= _CALIBRATION_SAMPLES:
                self._set_joystick_center(
                    self._calibration_sum_x / self._calibration_samples,
                    self._calibration_sum_y / self._calibration_samples,
                )
                self.joystick_cal_done.emit()
            return
        if self._axis_norm_x._center is None or self._axis_norm_y._center is None:
            self._axis_norm_x.set_center(self._center_x)
            self._axis_norm_y.set_center(self._center_y)

        if self._axis_norm_x.center != self._center_x:
            self._axis_norm_x.set_center(self._center_x)
        if self._axis_norm_y.center != self._center_y:
            self._axis_norm_y.set_center(self._center_y)
        nx = self._axis_norm_x.normalize(x_axis)
        ny = self._axis_norm_y.normalize(y_axis)
        if self._invert_x:
            nx = -nx
        if self._invert_y:
            ny = -ny
        self._joystick_x_raw = int(x_raw)
        self._joystick_y_raw = int(y_raw)
        self._joystick_x_axis = int(x_axis)
        self._joystick_y_axis = int(y_axis)
        self._joystick_norm_x = nx
        self._joystick_norm_y = ny
        self._joystick_sample_t = time.monotonic()
        self._joystick_sample_ready = True

    def _joystick_axis_target(self, axis: str, norm: float) -> float:
        active_attr = f"_joystick_{axis}_active"
        sign_attr = f"_joystick_{axis}_sign"
        accum_attr = "_dx_accum" if axis == "x" else "_dy_accum"
        active = bool(getattr(self, active_attr))
        old_sign = int(getattr(self, sign_attr))
        current_sign = self._sign(norm)
        magnitude = abs(norm)
        enter_threshold = self._deadzone
        exit_threshold = self._deadzone * _JOYSTICK_RELEASE_FACTOR

        if active and current_sign != 0 and current_sign != old_sign:
            setattr(self, accum_attr, 0.0)
            active = False
            old_sign = 0

        if active and (current_sign == 0 or magnitude < exit_threshold):
            setattr(self, accum_attr, 0.0)
            active = False
            old_sign = 0

        if not active and current_sign != 0 and magnitude >= enter_threshold:
            active = True
            old_sign = current_sign

        setattr(self, active_attr, active)
        setattr(self, sign_attr, old_sign)
        if not active:
            return 0.0
        return _joystick_curve(norm, self._deadzone, self._joystick_curve_name, self._joystick_expo_strength)

    def _smooth_joystick_target(self, previous: float, target: float, *, active: bool, sign_changed: bool) -> float:
        if not active or target == 0.0:
            return 0.0
        if sign_changed or (previous != 0.0 and self._sign(previous) != self._sign(target)):
            previous = 0.0
        alpha = self._joystick_dispatch.target_alpha
        return previous + alpha * (target - previous)

    @Slot()
    def _dispatch_joystick(self) -> None:
        self._dispatch_joystick_at(time.monotonic())

    def _dispatch_joystick_at(self, now: float) -> None:
        if not self._joystick_sample_ready:
            return
        if now - self._joystick_sample_t > _JOYSTICK_SAMPLE_TIMEOUT_S:
            self._clear_joystick_motion_state(clear_sample=True)
            return
        profile = self._obj.current_profile()
        self._refresh_motion_settings_from_config()
        dispatch = self._joystick_dispatch
        dt = (
            dispatch.interval_s
            if self._last_joystick_dispatch_t <= 0.0
            else now - self._last_joystick_dispatch_t
        )
        dt = max(0.0, min(_JOYSTICK_MAX_DISPATCH_DT_S, dt))
        if dt <= 0.0:
            return
        self._last_joystick_dispatch_t = now

        x_sign_before = self._joystick_x_sign
        y_sign_before = self._joystick_y_sign
        vx_target = self._joystick_axis_target("x", self._joystick_norm_x)
        vy_target = self._joystick_axis_target("y", self._joystick_norm_y)
        x_sign_changed = x_sign_before != 0 and self._joystick_x_sign != 0 and self._joystick_x_sign != x_sign_before
        y_sign_changed = y_sign_before != 0 and self._joystick_y_sign != 0 and self._joystick_y_sign != y_sign_before
        self._vx_filtered = self._smooth_joystick_target(
            self._vx_filtered,
            vx_target,
            active=self._joystick_x_active,
            sign_changed=x_sign_changed,
        )
        self._vy_filtered = self._smooth_joystick_target(
            self._vy_filtered,
            vy_target,
            active=self._joystick_y_active,
            sign_changed=y_sign_changed,
        )
        if not self._joystick_x_active:
            self._dx_accum = 0.0
        if not self._joystick_y_active:
            self._dy_accum = 0.0

        if vx_target == 0.0 and vy_target == 0.0:
            if not self._joystick_x_active:
                self._dx_accum = 0.0
            if not self._joystick_y_active:
                self._dy_accum = 0.0
            self._joystick_pending_since_t = None
            return

        steps_per_second_x, steps_per_second_y = self._derived_pan_steps_per_second_xy(profile)
        sensitivity = self._joystick_sensitivity_pct / 100.0
        self._dx_accum += self._vx_filtered * steps_per_second_x * sensitivity * dt
        self._dy_accum += self._vy_filtered * steps_per_second_y * sensitivity * dt
        dx, _ = self._take_whole_steps(self._dx_accum)
        dy, _ = self._take_whole_steps(self._dy_accum)
        if dx == 0 and dy == 0:
            self._joystick_pending_since_t = None
            return

        if self._joystick_pending_since_t is None:
            self._joystick_pending_since_t = now
        pending_s = now - self._joystick_pending_since_t
        should_send = max(abs(dx), abs(dy)) >= dispatch.min_command_steps
        should_send = should_send or pending_s >= dispatch.force_command_s
        if not should_send:
            return

        blocked = not self._move_rel_checked(dx, dy, 0, apply_backlash=False, coalesce=True)
        if blocked:
            self._dx_accum = 0.0
            self._dy_accum = 0.0
        else:
            self._dx_accum -= dx
            self._dy_accum -= dy
        self._joystick_pending_since_t = None

    @Slot(int)
    def on_encoder_stepped(self, delta: int) -> None:
        """Converts encoder ticks into calibrated Z motor moves using the active objective focus-stack step size and encoder multiplier."""

        self._encoder_accum += delta
        if self._calibration_encoder_step_active:
            # During DoF calibration: temp fixed step size is used
            move_steps = _CALIBRATION_Z_ENCODER_STEP
        else:
            profile = self._obj.current_profile()
            move_steps = max(
                1,
                int(round(max(1, int(profile.focus_stack_step)) * self._z_encoder_step_multiplier)),
            )
        trigger_units = max(1, int(round(ENCODER_TRIGGER_UNITS * 100 / self._encoder_sensitivity_pct)))
        while abs(self._encoder_accum) >= trigger_units:
            direction = 1 if self._encoder_accum > 0 else -1
            self.move_z(direction * move_steps)
            self._encoder_accum -= direction * trigger_units

    @Slot(int)
    def setZEncoderSensitivityPct(self, value: int) -> None:
        self._encoder_sensitivity_pct = max(25, min(400, int(value)))

    @Slot(str)
    def setJoystickCurve(self, value: str) -> None:
        if value in {"linear", "exponential", "scurve"}:
            self._joystick_curve_name = value

    @Slot(int)
    def setJoystickExpoStrength(self, value: int) -> None:
        self._joystick_expo_strength = max(0, min(100, int(value)))

    @Slot(int)
    def setJoystickSensitivityPct(self, value: int) -> None:
        self._joystick_sensitivity_pct = max(10, min(300, int(value)))

    @Slot(int)
    def setMaxPanSpeedPxPerSec(self, value: int) -> None:
        self._max_pan_speed_px_per_sec = max(10, min(4000, int(value)))

    @Slot(float)
    def setZEncoderStepMultiplier(self, value: float) -> None:
        self._z_encoder_step_multiplier = max(0.25, min(4.0, float(value)))

    @Slot(bool)
    def set_calibration_encoder_step_active(self, active: bool) -> None:
        """Use a fixed fine Z step per encoder tick while DoF calibrating."""
        self._calibration_encoder_step_active = bool(active)

    def _stage_um_per_step(self, axis: str) -> float:
        if self._config is None:
            return _STAGE_UM_PER_STEP_FALLBACK
        key = "motor.stage_um_per_step_y" if axis == "y" else "motor.stage_um_per_step_x"
        other_key = "motor.stage_um_per_step_x" if axis == "y" else "motor.stage_um_per_step_y"
        value = float(self._config.get(key, 0.0))
        if value > 0.0:
            return value
        other = float(self._config.get(other_key, 0.0))
        return other if other > 0.0 else _STAGE_UM_PER_STEP_FALLBACK

    def _derived_pan_steps_per_second_xy(self, profile) -> tuple[float, float]:
        """Return per-axis command rates for joystick pan motion."""
        um_per_pixel = max(1e-6, float(profile.um_per_pixel))
        speed = max(1.0, float(self._max_pan_speed_px_per_sec))
        x_step_um = max(1e-6, self._stage_um_per_step("x"))
        y_step_um = max(1e-6, self._stage_um_per_step("y"))
        return (
            speed * um_per_pixel / x_step_um * _JOYSTICK_PAN_COMMAND_BOOST,
            speed * um_per_pixel / y_step_um * _JOYSTICK_PAN_COMMAND_BOOST,
        )

    @Slot(int, int)
    def move_rel_xy(self, dx: int, dy: int) -> bool:
        """Wrapper for XY-only relative moves (used by touch input)."""
        return self.move_rel(dx, dy, 0)

    @Slot(int)
    def move_z(self, steps: int) -> bool:
        """Move Z by raw steps, used by encoder, UI and automation routines."""
        return self._move_rel_checked(0, 0, int(steps), apply_backlash=True)

    def move_z_blocking(self, steps: int) -> bool:
        """Move Z synchronously for autofocus while leaving manual motion live."""
        return self._move_rel_checked_blocking(0, 0, int(steps), apply_backlash=True)

    def move_rel_blocking(self, dx: int, dy: int, dz: int = 0, source: str = "manual") -> bool:
        """Move XYZ synchronously for automation while leaving manual motion live."""
        return self._move_rel_checked_blocking(
            int(dx),
            int(dy),
            int(dz),
            source=source,
            apply_backlash=True,
        )

    @Slot(int, int, int)
    def move_rel(self, dx: int, dy: int, dz: int, source: str = "manual") -> bool:
        """Move XYZ by relative steps with safety gates and backlash compensation."""
        return self._move_rel_checked(int(dx), int(dy), int(dz), source=source, apply_backlash=True)

    @Slot(int, int, int, result=bool)
    def calibration_move_rel(self, dx: int, dy: int, dz: int) -> bool:
        """Move XYZ for calibration without applying backlash compensation."""
        return self._move_rel_checked(int(dx), int(dy), int(dz), source="calibration", apply_backlash=False)

    @Slot(bool)
    def on_endstop_triggered(self, triggered: bool) -> None:
        """Receive endstop state from EndstopDriver."""
        self._endstop = triggered

    @Slot()
    def emergency_stop(self) -> None:
        """Immediately halt all motor movement."""
        self._clear_joystick_motion_state(clear_sample=True)
        self._sb.stop_motors()

    @Slot()
    def deenergize_motors(self) -> None:
        """Release motor current after clearing queued manual motion intent."""
        self._clear_joystick_motion_state(clear_sample=True)
        self._encoder_accum = 0
        if hasattr(self._sb, "release_motors"):
            self._sb.release_motors()
        else:
            self._sb.stop_motors()
        # The stage can drift / moved by hand, so invalidate backlash stage
        self.invalidate_backlash_history()

    @Slot()
    def invalidate_backlash_history(self) -> None:
        """Forget which side of the gear lash band each axis is resting on."""
        self._slack_x = 0.0
        self._slack_y = 0.0
        self._slack_z = 0.0
        self._emit_backlash_slack_changed()

    # Joystick calibration
    @Property(float, notify=joystick_center_changed)
    def joystickCenterX(self) -> float:
        return self._center_x if self._center_x is not None else 0.0

    @Property(float, notify=joystick_center_changed)
    def joystickCenterY(self) -> float:
        return self._center_y if self._center_y is not None else 0.0

    @Slot()
    def startJoystickCal(self) -> None:
        """Reset calibration, then ADC samples set new center."""
        self._center_x = None
        self._center_y = None
        self._calibration_samples = 0
        self._calibration_sum_x = 0.0
        self._calibration_sum_y = 0.0
        self._axis_norm_x.set_center(None)
        self._axis_norm_y.set_center(None)
        self._clear_joystick_motion_state(clear_sample=True)

    @Slot(bool)
    def setJoystickSwapXY(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._swap_xy:
            return
        self._swap_xy = enabled
        self._clear_joystick_motion_state(clear_sample=True)
        if self._center_x is not None and self._center_y is not None:
            self._set_joystick_center(self._center_y, self._center_x)
        else:
            self.startJoystickCal()

    @Slot(bool)
    def setJoystickInvertX(self, enabled: bool) -> None:
        self._invert_x = bool(enabled)
        self._clear_joystick_motion_state(clear_sample=True)

    @Slot(bool)
    def setJoystickInvertY(self, enabled: bool) -> None:
        self._invert_y = bool(enabled)
        self._clear_joystick_motion_state(clear_sample=True)

    def _map_joystick_raw_axes(self, x_raw: int, y_raw: int) -> tuple[int, int]:
        if self._swap_xy:
            return int(y_raw), int(x_raw)
        return int(x_raw), int(y_raw)

    def _set_joystick_center(self, cx: float, cy: float) -> None:
        self._center_x = float(cx)
        self._center_y = float(cy)
        self._axis_norm_x.set_center(self._center_x)
        self._axis_norm_y.set_center(self._center_y)
        self._clear_joystick_motion_state(clear_sample=True)
        self.joystick_center_changed.emit()

    @Property(float, notify=deadzone_changed)
    def deadzone(self) -> float:
        return self._deadzone

    @Slot(float)
    def setDeadzone(self, value: float) -> None:
        self._deadzone = max(0.01, min(0.5, value))
        self._clear_joystick_motion_state(clear_sample=True)
        self.deadzone_changed.emit()
