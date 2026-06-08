"""Evaluation: Motion accuracy and compensation effectiveness by commanding moves of a known number of steps and 
measuring the resulting optical displacement, then reversing and measuring the residual displacement.

Note: Partially AI-generated.
"""

from __future__ import annotations

from pathlib import Path

from retroscope.evaluation.compensation import CompensatedMover, MODES
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] motion_accuracy: no camera frames available, aborting.")
        return None

    axes = C.parse_axes(ctx, default="xy", allow_z=True)
    modes = [m for m in str(ctx.arg("modes", "none,sign,hysteresis")).split(",") if m in MODES]
    steps_list = ctx.arg_list_int("steps", [200])
    reps = int(ctx.arg("reps", 5, int))
    settle_s = float(ctx.arg("settle_ms", 300, int)) / 1000.0
    upp = ctx.um_per_pixel()

    mover = CompensatedMover(
        ctx.sangaboard, ctx.backlash_xyz(),
        max_excursion=int(ctx.arg("max_excursion", 20000, int)),
    )
    rw = ResultWriter("motion_accuracy")

    for axis in axes:
        scale = ctx.stage_um_per_step(axis)
        for mode in modes:
            for steps in steps_list:
                for rep in range(reps):
                    mover.reset()
                    fwd = C.measure_forward(ctx, mover, axis, steps, mode, settle_s)
                    if fwd is None:
                        print("[eval] motion_accuracy: frame grab failed, aborting.")
                        return rw.save(ctx.out_dir)
                    # reverse from current position back to start under the same mode
                    mover.move_axis(axis, -steps, mode)
                    import time
                    time.sleep(settle_s)
                    back = ctx.camera_svc.get_latest_frame()
                    resid_px = 0.0
                    if back is not None:
                        from retroscope.evaluation import measure as _m
                        resid_px, _, _ = _m.displacement_px(fwd["ref"], back)
                    commanded_um = abs(steps) * scale
                    measured_um = fwd["disp_px"] * upp
                    rw.add(
                        axis=C.AXIS_NAME[axis], mode=mode, commanded_steps=steps, rep=rep,
                        fwd_px=round(fwd["disp_px"], 3),
                        measured_um=round(measured_um, 4),
                        commanded_um=round(commanded_um, 4),
                        error_um=round(measured_um - commanded_um, 4),
                        residual_px=round(resid_px, 3),
                        residual_um=round(resid_px * upp, 4),
                    )
                    mover.return_to_start()

    rw.summarize(
        ["axis", "mode", "commanded_steps"],
        ["fwd_px", "measured_um", "commanded_um", "error_um", "residual_px", "residual_um"],
    )
    path = rw.save(ctx.out_dir)
    print(f"[eval] motion_accuracy -> {path}")
    return path
