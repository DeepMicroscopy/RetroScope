"""Evaluation experiment: calibration repeatability.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time
from pathlib import Path

from retroscope.evaluation.compensation import CompensatedMover, ExcursionGuard
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C
from retroscope.evaluation.experiments.stage_scale import measure_series


def _round_or_none(value, digits: int):
    return None if value is None else round(value, digits)


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
    rw = ResultWriter("calibration_repeat", default_fields=ctx.result_metadata())

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

    rw.summarize(["quantity"], ["value"])
    path = rw.save(ctx.out_dir)
    print(f"[eval] calibration_repeat -> {path}")
    return path
