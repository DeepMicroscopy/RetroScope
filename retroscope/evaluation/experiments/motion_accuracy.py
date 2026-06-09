"""Evaluation: Motion accuracy and compensation effectiveness by commanding moves of a known number of steps and 
measuring the resulting optical displacement, then reversing and measuring the residual displacement.

Note: Partially AI-generated.
"""

from __future__ import annotations

import time
from pathlib import Path

from retroscope.evaluation import measure as _m
from retroscope.evaluation.compensation import CompensatedMover, ExcursionGuard, MODES
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C


def _round_or_none(value, digits: int):
    return None if value is None else round(value, digits)


def _reason(*items) -> str:
    reasons = [getattr(item, "reason", "") for item in items if item is not None and not item.valid]
    return ";".join(r for r in reasons if r)


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] motion_accuracy: no camera frames available, aborting.")
        return None

    requested_axes = C.parse_axes(ctx, default="xy", allow_z=True)
    if 2 in requested_axes:
        print("[eval] motion_accuracy: skipping Z, optical lateral displacement is only measured for X/Y.")
    axes = [axis for axis in requested_axes if axis in (0, 1)]
    if not axes:
        print("[eval] motion_accuracy: no measurable X/Y axes selected, aborting.")
        return None

    modes = [m for m in str(ctx.arg("modes", "none,sign,hysteresis")).split(",") if m in MODES]
    steps_list = ctx.arg_list_int("steps", [200])
    reps = int(ctx.arg("reps", 5, int))
    settle_s = float(ctx.arg("settle_ms", 1500, int)) / 1000.0
    upp = ctx.um_per_pixel()

    mover = CompensatedMover(
        ctx.sangaboard, ctx.backlash_xyz(),
        max_excursion=int(ctx.arg("max_excursion", 20000, int)),
    )
    rw = ResultWriter("motion_accuracy", default_fields=ctx.result_metadata())

    try:
        for axis in axes:
            scale = ctx.stage_um_per_step(axis)
            for mode in modes:
                for steps in steps_list:
                    for rep in range(reps):
                        mover.reset()
                        fwd = C.measure_forward(ctx, mover, axis, steps, mode, settle_s)
                        if fwd is None:
                            print("[eval] motion_accuracy: frame grab failed, aborting.")
                            try:
                                mover.return_to_start()
                            except Exception:
                                pass
                            return rw.save(ctx.out_dir)
                        # reverse from current position back to start under the same mode
                        mover.move_axis(axis, -steps, mode)
                        time.sleep(settle_s)
                        back = _m.grab_fresh(ctx.camera_svc)  # new, post-settle frame
                        resid = None
                        if back is not None:
                            resid = _m.measure_displacement(
                                fwd["ref"],
                                back,
                                **C.displacement_options(ctx, residual=True),
                            )
                        fwd_m = fwd["measurement"]
                        resid_px = resid.magnitude_px if resid is not None else 0.0
                        commanded_um = abs(steps) * scale
                        measured_um = fwd_m.axis_px(axis) * upp
                        valid = fwd_m.valid and (resid.valid if resid is not None else False)
                        reason = _reason(fwd_m, resid)
                        if resid is None:
                            reason = ";".join(filter(None, [reason, "residual_frame_missing"]))
                        rw.add(
                            axis=C.AXIS_NAME[axis], mode=mode, commanded_steps=steps, rep=rep,
                            valid=valid,
                            reason=reason,
                            fwd_px=round(fwd_m.axis_px(axis), 3),
                            dx_px=round(fwd_m.dx_px, 3),
                            dy_px=round(fwd_m.dy_px, 3),
                            cross_axis_px=round(fwd_m.cross_axis_px(axis), 3),
                            phase_response=round(fwd_m.phase_response, 4),
                            template_score=_round_or_none(fwd_m.template_score, 4),
                            measured_um=round(measured_um, 4),
                            commanded_um=round(commanded_um, 4),
                            error_um=round(measured_um - commanded_um, 4),
                            residual_px=round(resid_px, 3),
                            residual_um=round(resid_px * upp, 4),
                            residual_phase_response=_round_or_none(
                                resid.phase_response if resid is not None else None, 4
                            ),
                        )
                        mover.return_to_start()
    except (RuntimeError, ExcursionGuard) as e:
        print(f"[eval] motion_accuracy: aborted after a move error: {e}")
        try:
            mover.return_to_start()
        except Exception:
            pass

    rw.summarize(
        ["axis", "mode", "commanded_steps"],
        ["fwd_px", "measured_um", "commanded_um", "error_um", "residual_px", "residual_um"],
    )
    path = rw.save(ctx.out_dir)
    print(f"[eval] motion_accuracy -> {path}")
    return path
