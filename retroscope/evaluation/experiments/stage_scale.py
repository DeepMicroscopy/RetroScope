"""Evaluation: Stage scale (um per step) by commanding moves of a known number of steps and measuring the resulting optical displacement.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time
from pathlib import Path

from retroscope.evaluation import measure
from retroscope.evaluation.compensation import CompensatedMover
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C
from retroscope.services.stage_calibration import stage_um_per_step


def measure_series(ctx, mover, axis: int, steps: int, reps: int, settle_s: float) -> list[float]:
    upp = ctx.um_per_pixel()
    results: list[float] = []
    mover.move_axis(axis, steps, "none")
    time.sleep(settle_s)
    for _ in range(reps):
        ref = measure.grab_frame(ctx.camera_svc)
        mover.move_axis(axis, steps, "none")
        time.sleep(settle_s)
        after = measure.grab_frame(ctx.camera_svc)
        if ref is None or after is None:
            break
        disp_px, _, _ = measure.displacement_px(ref, after)
        results.append(stage_um_per_step(disp_px, upp, steps))
    mover.return_to_start()
    return results


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] stage_scale: no camera frames available, aborting.")
        return None

    axes = C.parse_axes(ctx, default="xy")
    steps = int(ctx.arg("steps", 300, int))
    reps = int(ctx.arg("reps", 8, int))
    settle_s = float(ctx.arg("settle_ms", 300, int)) / 1000.0

    mover = CompensatedMover(
        ctx.sangaboard, ctx.backlash_xyz(),
        max_excursion=int(ctx.arg("max_excursion", 20000, int)),
    )
    rw = ResultWriter("stage_scale")

    for axis in axes:
        mover.reset()
        series = measure_series(ctx, mover, axis, steps, reps, settle_s)
        for rep, val in enumerate(series):
            rw.add(axis=C.AXIS_NAME[axis], commanded_steps=steps, rep=rep,
                   um_per_step=round(val, 5))

    rw.summarize(["axis", "commanded_steps"], ["um_per_step"])
    path = rw.save(ctx.out_dir)
    print(f"[eval] stage_scale -> {path}")
    return path
