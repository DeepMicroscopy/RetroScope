"""Evaluation experiment: calibration repeatability.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from retroscope.evaluation import measure
from retroscope.evaluation.compensation import CompensatedMover, ExcursionGuard
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C
from retroscope.evaluation.experiments.stage_scale import measure_series


def _round_or_none(value, digits: int):
    return None if value is None else round(value, digits)


def _pixel_scale_two_point(ctx, rw, marks: int) -> None:
    """Operator marks two points of a known separation on a saved frame, then repeat."""
    frame = measure.grab_frame(ctx.camera_svc, native=True)
    if frame is None:
        print("[eval] pixel_scale: no frame, skipping.")
        return
    out = Path(ctx.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img_path = out / "pixel_scale_reference.png"
    try:
        import cv2

        cv2.imwrite(str(img_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        print(f"[eval] pixel_scale: open {img_path} and read off two points of a known distance.")
    except Exception:
        print("[eval] pixel_scale: could not save reference image.")
    for i in range(marks):
        print(f"[eval] pixel_scale mark {i + 1}/{marks}: enter 'x1 y1 x2 y2 known_um' (blank to stop)")
        raw = C.prompt("  > ").strip()
        if raw == "":
            break
        try:
            x1, y1, x2, y2, known_um = (float(v) for v in raw.split())
        except ValueError:
            print("  (could not parse, expected five numbers)")
            continue
        dist_px = float(np.hypot(x2 - x1, y2 - y1))
        if dist_px <= 0 or known_um <= 0:
            continue
        rw.add(quantity="pixel_scale_um_per_px", rep=i, value=round(known_um / dist_px, 5))


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] calibration_repeat: no camera frames available, aborting.")
        return None

    axes = C.parse_axes(ctx, default="xy")
    stage_steps = int(ctx.arg("stage_steps", 300, int))
    backlash_steps = int(ctx.arg("backlash_steps", 300, int))
    reps = int(ctx.arg("reps", 5, int))
    settle_s = float(ctx.arg("settle_ms", 1500, int)) / 1000.0
    upp = ctx.um_per_pixel()

    mover = CompensatedMover(
        ctx.sangaboard, ctx.backlash_xyz(),
        max_excursion=int(ctx.arg("max_excursion", 20000, int)),
    )
    rw = ResultWriter("calibration_repeat")

    try:
        # Stage-scale repeatability (per axis)
        for axis in axes:
            mover.reset()
            for rep, item in enumerate(measure_series(ctx, mover, axis, stage_steps, reps, settle_s)):
                rw.add(quantity=f"stage_scale_{C.AXIS_NAME[axis]}_um_per_step", rep=rep,
                       valid=item.get("valid", False),
                       reason=item.get("reason", ""),
                       value=_round_or_none(item.get("um_per_step"), 5))

        # Backlash repeatability
        for axis in axes:
            mover.reset()
            for rep in range(reps):
                res = C.measure_reversal_residual(ctx, mover, axis, backlash_steps, "none", settle_s)
                if res is None:
                    break
                measurement = res["measurement"]
                rw.add(quantity=f"backlash_{C.AXIS_NAME[axis]}_residual_um", rep=rep,
                       valid=measurement.valid,
                       reason=measurement.reason,
                       value=round(res["residual_px"] * upp, 4),
                       phase_response=round(measurement.phase_response, 4),
                       template_score=_round_or_none(measurement.template_score, 4))
                mover.return_to_start()
                time.sleep(settle_s)
    except (RuntimeError, ExcursionGuard) as e:
        print(f"[eval] calibration_repeat: motor section aborted after a move error: {e}")
        try:
            mover.return_to_start()
        except Exception:
            pass

    # Operator two-point pixel scale
    _pixel_scale_two_point(ctx, rw, marks=int(ctx.arg("pixel_marks", reps, int)))

    # Derived-objective cross-check
    derived = ctx.profile().um_per_pixel
    print(f"[eval] derived pixel scale for objective '{ctx.profile().name}' = {derived:.5f} um/px")
    measured = C.prompt_float("  enter directly-measured um/px for this objective (blank to skip): ")
    if measured is not None:
        rw.add(quantity="derived_objective_check_derived", rep=0, value=round(derived, 5))
        rw.add(quantity="derived_objective_check_measured", rep=0, value=round(measured, 5))

    rw.summarize(["quantity"], ["value"])
    path = rw.save(ctx.out_dir)
    print(f"[eval] calibration_repeat -> {path}")
    return path
