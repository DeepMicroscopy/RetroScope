"""Evaluation: Workflow Reliability (autofocus, focus stacking, tile scanning, measurement, gallery)

Note: Partially AI-generated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from retroscope.evaluation import measure
from retroscope.evaluation.csv_io import ResultWriter
from retroscope.evaluation.experiments import _common as C
from retroscope.evaluation.service_drive import run_async
from retroscope.services import ome_tiff


def _source_plane_count(path: str) -> int:
    try:
        md = ome_tiff.read_metadata(Path(path))
    except Exception:
        return 0
    series = md.get("ome_series", []) or []
    if not series:
        return 0
    return max((len(s.get("ifds", []) or []) for s in series), default=0)


def _run_autofocus(ctx, rw, reps: int, offset: int) -> None:
    af = ctx.autofocus_svc
    sign = 1
    for rep in range(reps):
        # vary the starting Z position
        if offset and hasattr(ctx.motion_ctrl, "move_z_blocking"):
            C.call_main(ctx, lambda sign=sign: ctx.motion_ctrl.move_z_blocking(sign * offset))
        status, payload = run_async(
            ctx.invoker, af.start_autofocus,
            success_signals=[af.finished], failure_signals=[af.failed],
            timeout_s=float(ctx.arg("af_timeout_s", 60, int)),
        )
        ok = status == "success"
        rw.add(workflow="autofocus", rep=rep, success=int(ok), status=status,
               reason="" if ok else str(payload or status))
        sign *= -1


def _run_focus_stack(ctx, rw, reps: int) -> None:
    fs = ctx.focus_stacker_svc
    if fs is None:
        return
    zhr = int(ctx.arg("fs_half_range", 30, int))
    step = int(ctx.arg("fs_step", 5, int))
    expected = len(list(range(-zhr, zhr + 1, step)))
    for rep in range(reps):
        status, payload = run_async(
            ctx.invoker, lambda: fs.start(z_half_range=zhr, step_size=step),
            success_signals=[fs.finished],
            timeout_s=float(ctx.arg("fs_timeout_s", 180, int)),
        )
        path = str(payload or "")
        planes = _source_plane_count(path) if path else 0
        ok = bool(path) and planes >= expected
        reason = "" if ok else (f"{planes}/{expected} planes" if path else status)
        rw.add(workflow="focus_stacking", rep=rep, success=int(ok), status=status, reason=reason)


def _run_tile_scan(ctx, rw, reps: int) -> None:
    ts = ctx.tile_scanner_svc
    if ts is None:
        return
    cols = int(ctx.arg("ts_cols", 3, int))
    rows = int(ctx.arg("ts_rows", 2, int))
    overlap = float(ctx.arg("ts_overlap", 0.2, float))
    expected = cols * rows
    for rep in range(reps):
        status, payload = run_async(
            ctx.invoker,
            lambda: ts.start(cols, rows, overlap, "raster", False, False, True, 300),
            success_signals=[ts.scan_saved],
            timeout_s=float(ctx.arg("ts_timeout_s", 300, int)),
        )
        path = str(payload or "")
        tiles = _source_plane_count(path) if path else 0
        ok = bool(path) and tiles >= expected
        reason = "" if ok else (f"{tiles}/{expected} tiles" if path else status)
        rw.add(workflow="tile_scanning", rep=rep, success=int(ok), status=status, reason=reason)


def _run_measurement(ctx, rw, reps: int) -> None:
    upp = ctx.um_per_pixel()
    tol = float(ctx.arg("measure_tol_pct", 5.0, float)) / 100.0
    for rep in range(reps):
        print(f"[eval] measurement {rep + 1}/{reps}: enter 'x1 y1 x2 y2 known_um' (blank to stop)")
        raw = C.prompt("  > ").strip()
        if raw == "":
            break
        try:
            x1, y1, x2, y2, known = (float(v) for v in raw.split())
        except ValueError:
            continue
        meas_um = float(np.hypot(x2 - x1, y2 - y1)) * upp
        ok = known > 0 and abs(meas_um - known) <= tol * known
        rw.add(workflow="measurement", rep=rep, success=int(ok), status="measured",
               reason="" if ok else f"measured {meas_um:.2f} vs known {known:.2f} um")


def _run_gallery(ctx, rw) -> None:
    print("[eval] gallery: exercise the gallery with a large capture set in the UI.")
    res = C.prompt("  enter 'pass' or 'fail: reason' (blank to skip): ").strip()
    if res == "":
        return
    ok = res.lower().startswith("pass")
    rw.add(workflow="gallery", rep=0, success=int(ok), status="operator",
           reason="" if ok else res)


def run(ctx) -> Path | None:
    if not C.wait_for_frames(ctx):
        print("[eval] workflow_reliability: no camera frames available, aborting.")
        return None

    reps = int(ctx.arg("reps", 10, int))
    which = str(ctx.arg("workflows", "autofocus,focus_stacking,tile_scanning,measurement,gallery"))
    selected = {w.strip() for w in which.split(",") if w.strip()}
    rw = ResultWriter("workflow_reliability")

    if "autofocus" in selected:
        _run_autofocus(ctx, rw, reps, offset=int(ctx.arg("af_z_offset", 80, int)))
    if "focus_stacking" in selected:
        _run_focus_stack(ctx, rw, reps)
    if "tile_scanning" in selected:
        _run_tile_scan(ctx, rw, reps)
    if "measurement" in selected:
        _run_measurement(ctx, rw, reps)
    if "gallery" in selected:
        _run_gallery(ctx, rw)

    rw.summarize(["workflow"], ["success"])
    path = rw.save(ctx.out_dir)
    print(f"[eval] workflow_reliability -> {path}")
    return path
