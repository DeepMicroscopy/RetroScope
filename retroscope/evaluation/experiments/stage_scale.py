"""Evaluation: Stage scale (um per step) by commanding moves of a known number of steps and measuring the resulting optical displacement.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time
from pathlib import Path

from retroscope.evaluation import measure
from retroscope.evaluation.compensation import CompensatedMover, ExcursionGuard
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C
from retroscope.services.stage_calibration import stage_um_per_step


def _round_or_none(value, digits: int):
    return None if value is None else round(value, digits)


def measure_series(ctx, mover, axis: int, steps: int, reps: int, settle_s: float) -> list[dict]:
    upp = ctx.um_per_pixel()
    results: list[dict] = []
    mover.move_axis(axis, steps, "none")
    time.sleep(settle_s)
    for _rep in range(reps):
        ref = measure.grab_fresh(ctx.camera_svc)
        mover.move_axis(axis, steps, "none")
        time.sleep(settle_s)
        after = measure.grab_fresh(ctx.camera_svc)  # guaranteed a new, post-settle frame
        if ref is None or after is None:
            results.append({
                "valid": False,
                "reason": "frame_missing",
                "um_per_step": None,
                "measurement": None,
            })
            break
        result = measure.measure_displacement(
            ref,
            after,
            **C.displacement_options(ctx, axis=axis),
        )
        results.append({
            "valid": result.valid,
            "reason": result.reason,
            "um_per_step": stage_um_per_step(result.axis_px(axis), upp, steps),
            "measurement": result,
        })
    mover.return_to_start()
    return results


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] stage_scale: no camera frames available, aborting.")
        return None

    axes = C.parse_axes(ctx, default="xy")
    steps = int(ctx.arg("steps", 300, int))
    reps = int(ctx.arg("reps", 8, int))
    settle_s = float(ctx.arg("settle_ms", 1500, int)) / 1000.0

    mover = CompensatedMover(
        ctx.sangaboard, ctx.backlash_xyz(),
        max_excursion=int(ctx.arg("max_excursion", 20000, int)),
    )
    rw = ResultWriter("stage_scale", default_fields=ctx.result_metadata())

    try:
        for axis in axes:
            mover.reset()
            series = measure_series(ctx, mover, axis, steps, reps, settle_s)
            for rep, item in enumerate(series):
                measurement = item.get("measurement")
                rw.add(axis=C.AXIS_NAME[axis], commanded_steps=steps, rep=rep,
                       valid=item.get("valid", False),
                       reason=item.get("reason", ""),
                       um_per_step=_round_or_none(item.get("um_per_step"), 5),
                       measured_px=_round_or_none(
                           measurement.axis_px(axis) if measurement is not None else None, 3
                       ),
                       dx_px=_round_or_none(
                           measurement.dx_px if measurement is not None else None, 3
                       ),
                       dy_px=_round_or_none(
                           measurement.dy_px if measurement is not None else None, 3
                       ),
                       cross_axis_px=_round_or_none(
                           measurement.cross_axis_px(axis) if measurement is not None else None, 3
                       ),
                       phase_response=_round_or_none(
                           measurement.phase_response if measurement is not None else None, 4
                       ),
                       template_score=_round_or_none(
                           measurement.template_score if measurement is not None else None, 4
                       ))
    except (RuntimeError, ExcursionGuard) as e:
        print(f"[eval] stage_scale: aborted after a move error: {e}")
        try:
            mover.return_to_start()
        except Exception:
            pass

    rw.summarize(["axis", "commanded_steps"], ["um_per_step"])
    path = rw.save(ctx.out_dir)
    print(f"[eval] stage_scale -> {path}")
    return path
