"""Shared helpers for the evaluation experiments."""

from __future__ import annotations

import time

from retroscope.evaluation import measure

AXIS_NAME = {0: "X", 1: "Y", 2: "Z"}
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def wait_for_frames(ctx, timeout_s: float | None = None) -> bool:
    if timeout_s is None:
        timeout_s = float(ctx.arg("frame_wait_s", 30, int))
    print(f"[eval] waiting up to {timeout_s:.0f}s for camera frames (make sure the Live view is open)...")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if ctx.camera_svc.get_latest_frame() is not None:
            return True
        time.sleep(0.1)
    return False


def parse_axes(ctx, default: str = "xy", allow_z: bool = False) -> list[int]:
    raw = str(ctx.arg("axes", default)).lower()
    axes = []
    for a in raw:
        if a in AXIS_INDEX:
            idx = AXIS_INDEX[a]
            if idx == 2 and not (allow_z and ctx.arg("include_z")):
                continue
            axes.append(idx)
    return axes or [0, 1]


def measure_forward(ctx, mover, axis: int, steps: int, mode: str, settle_s: float):
    ref = measure.grab_frame(ctx.camera_svc)
    if ref is None:
        return None
    mover.move_axis(axis, steps, mode)
    time.sleep(settle_s)
    after = measure.grab_frame(ctx.camera_svc)
    if after is None:
        return None
    disp_px, dx, dy = measure.displacement_px(ref, after)
    return {"ref": ref, "after": after, "disp_px": disp_px, "dx": dx, "dy": dy}


def measure_reversal_residual(ctx, mover, axis: int, steps: int, mode: str, settle_s: float):
    ref = measure.grab_frame(ctx.camera_svc)
    if ref is None:
        return None
    mover.move_axis(axis, steps, mode)
    time.sleep(settle_s)
    mover.move_axis(axis, -steps, mode)
    time.sleep(settle_s)
    back = measure.grab_frame(ctx.camera_svc)
    if back is None:
        return None
    resid_px, dx, dy = measure.displacement_px(ref, back)
    return {"residual_px": resid_px, "dx": dx, "dy": dy}


def prompt(msg: str) -> str:
    try:
        return input(msg)
    except EOFError:
        return ""


def prompt_float(msg: str, default: float | None = None) -> float | None:
    raw = prompt(msg).strip()
    if raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default
