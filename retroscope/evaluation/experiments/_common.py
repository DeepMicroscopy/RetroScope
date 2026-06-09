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


def arg_bool(ctx, name: str, default: bool = False) -> bool:
    raw = ctx.arg(name, int(default))
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


def displacement_options(ctx, *, axis: int | None = None, residual: bool = False) -> dict:
    cross_axis_max = ctx.arg("cross_axis_max_px", None, float)
    return {
        "axis": axis,
        "min_phase_response": float(ctx.arg("min_phase_response", 0.15, float)),
        "min_axis_px": 0.0 if residual or axis is None else float(ctx.arg("min_axis_px", 0.5, float)),
        "cross_axis_max_px": cross_axis_max,
        "template_crop": int(ctx.arg("template_crop", 96, int)),
        "template_search_radius": int(ctx.arg("template_search_radius", 64, int)),
        "template_min_score": float(ctx.arg("template_min_score", 0.0, float)),
        "require_template": arg_bool(ctx, "require_template", False),
    }


def call_main(ctx, fn, *, timeout_s: float | None = None):
    if timeout_s is None:
        timeout_s = float(ctx.arg("main_thread_timeout_s", 10.0, float))
    if ctx.invoker is not None and hasattr(ctx.invoker, "call_sync"):
        return ctx.invoker.call_sync(fn, timeout_s=timeout_s)
    return fn()


def measure_forward(ctx, mover, axis: int, steps: int, mode: str, settle_s: float):
    ref = measure.grab_fresh(ctx.camera_svc)
    if ref is None:
        return None
    mover.move_axis(axis, steps, mode)
    time.sleep(settle_s)
    after = measure.grab_fresh(ctx.camera_svc)  # guaranteed a new, post-settle frame
    if after is None:
        return None
    result = measure.measure_displacement(
        ref,
        after,
        **displacement_options(ctx, axis=axis),
    )
    return {
        "ref": ref,
        "after": after,
        "measurement": result,
        "disp_px": result.axis_px(axis),
        "dx": result.dx_px,
        "dy": result.dy_px,
    }


def measure_reversal_residual(ctx, mover, axis: int, steps: int, mode: str, settle_s: float):
    ref = measure.grab_fresh(ctx.camera_svc)
    if ref is None:
        return None
    mover.move_axis(axis, steps, mode)
    time.sleep(settle_s)
    mover.move_axis(axis, -steps, mode)
    time.sleep(settle_s)
    back = measure.grab_fresh(ctx.camera_svc)  # guaranteed a new, post-settle frame
    if back is None:
        return None
    result = measure.measure_displacement(
        ref,
        back,
        **displacement_options(ctx, residual=True),
    )
    return {
        "measurement": result,
        "residual_px": result.magnitude_px,
        "dx": result.dx_px,
        "dy": result.dy_px,
    }


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
