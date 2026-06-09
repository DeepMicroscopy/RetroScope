"""Evaluation: Backlash-compensation move modes for the motion-accuracy evaluation.

Move modes:
- none: Send the requested delta unchanged.
- sign: Add the full backlash on a direction reversal (old sign-based model).
- hysteresis: The new slack-band model, identical to 'MotionController._plan_axis'.

Note: Partially AI-generated.
"""

from __future__ import annotations

MODES = ("none", "sign", "hysteresis")


def plan_none(delta: int) -> int:
    return int(delta)

def plan_sign(delta: int, last_dir: int, backlash: int) -> tuple[int, int]:
    """Sign-based model. 'last_dir' is -1/0/+1 (0 = unknown). Returns '(motor_delta, new_last_dir)'."""
    if delta == 0:
        return 0, last_dir
    sign = 1 if delta > 0 else -1
    motor = delta
    if backlash > 0 and last_dir != 0 and sign != last_dir:
        motor = delta + sign * int(backlash)
    return int(motor), sign

def plan_hysteresis(delta: int, slack: float, backlash: int) -> tuple[int, float]:
    """Slack-band model, identical to 'MotionController._plan_axis'. Returns '(motor_delta, new_slack)'."""
    if delta == 0 or backlash <= 0:
        return int(delta), float(slack)
    half = backlash / 2.0
    sign = 1 if delta > 0 else -1
    pre = sign * half - slack
    motor_delta = int(round(delta + pre))
    new_slack = sign * half
    return motor_delta, new_slack


class ExcursionGuard(Exception):
    """Raised when a commanded move would exceed the configured safe guards."""


class CompensatedMover:
    def __init__(self, sangaboard, backlash_xyz: tuple[int, int, int],
                 *, max_excursion: int = 20000, move_timeout_s: float = 30.0) -> None:
        self._sb = sangaboard
        self._backlash = tuple(int(b) for b in backlash_xyz)
        self._max_excursion = int(max_excursion)
        self._timeout = float(move_timeout_s)
        self.reset()

    def reset(self) -> None:
        self._slack = [0.0, 0.0, 0.0]
        self._last_dir = [0, 0, 0]
        self._requested_net = [0, 0, 0]
        self._motor_net = [0, 0, 0]

    def _send_axis(self, axis: int, motor_delta: int) -> None:
        vec = [0, 0, 0]
        vec[axis] = int(motor_delta)
        ok = self._sb.move_rel_blocking(vec[0], vec[1], vec[2], timeout=self._timeout)
        if ok is False:
            raise RuntimeError(f"sangaboard move_rel_blocking failed/timed out: {vec}")

    def move_axis(self, axis: int, delta: int, mode: str) -> int:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        requested_next = self._requested_net[axis] + int(delta)
        if abs(requested_next) > self._max_excursion:
            raise ExcursionGuard(
                f"axis {axis}: requested net {requested_next} exceeds limit {self._max_excursion}"
            )

        backlash = self._backlash[axis]
        new_last_dir = self._last_dir[axis]
        new_slack = self._slack[axis]
        if mode == "none":
            motor = plan_none(delta)
        elif mode == "sign":
            motor, new_last_dir = plan_sign(delta, self._last_dir[axis], backlash)
        else:
            motor, new_slack = plan_hysteresis(delta, self._slack[axis], backlash)

        motor_next = self._motor_net[axis] + int(motor)
        if abs(motor_next) > self._max_excursion:
            raise ExcursionGuard(
                f"axis {axis}: motor net {motor_next} exceeds limit {self._max_excursion}"
            )

        if motor != 0:
            self._send_axis(axis, motor)
        self._requested_net[axis] = requested_next
        self._motor_net[axis] = motor_next
        self._last_dir[axis] = new_last_dir
        self._slack[axis] = new_slack
        return int(motor)

    def return_to_start(self) -> None:
        for axis in range(3):
            net = self._motor_net[axis]
            if net != 0:
                self._send_axis(axis, -net)
                self._motor_net[axis] = 0
                self._requested_net[axis] = 0
        self.reset()
