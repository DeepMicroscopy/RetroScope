"""Evaluation: Dry-run of the motion/stage experiments against a 'fake rig'."""

from __future__ import annotations

import csv
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("PySide6")

from retroscope.evaluation.context import EvalContext
from retroscope.evaluation.experiments import motion_accuracy, stage_scale

PX_PER_STEP = 0.2  #  1 motor step = 0.2 px image shift


class FakeRig:
    """Acts as both the Sangaboard and the camera service."""

    def __init__(self):
        rng = np.random.default_rng(3)
        base = rng.integers(0, 255, size=(200, 320), dtype=np.uint8)
        self._base = np.stack([base, base, base], axis=-1)
        self.pos = [0, 0, 0]

    def move_rel_blocking(self, dx, dy, dz, timeout=None):
        self.pos[0] += dx
        self.pos[1] += dy
        self.pos[2] += dz
        return True

    def get_latest_frame(self):
        sx = int(round(self.pos[0] * PX_PER_STEP))
        sy = int(round(self.pos[1] * PX_PER_STEP))
        return np.roll(np.roll(self._base, sx, axis=1), sy, axis=0)

    def capture_native_frame(self, allow_tap_fallback=True):
        return self.get_latest_frame()


def _ctx(tmp_path, args):
    rig = FakeRig()
    profile = SimpleNamespace(name="4x", um_per_pixel=0.5, numerical_aperture=0.1,
                              backlash_x=100, backlash_y=200, backlash_z=20)
    config = SimpleNamespace(get=lambda k, d=None: {"motor.stage_um_per_step_x": 0.1,
                                                    "motor.stage_um_per_step_y": 0.1}.get(k, d))
    services = SimpleNamespace(
        config=config, camera_svc=rig, objective_mgr=SimpleNamespace(current_profile=lambda: profile),
        motion_ctrl=None, autofocus_svc=None, focus_stacker_svc=None, tile_scanner_svc=None,
        image_store=None,
    )
    return EvalContext(services=services, sangaboard=rig, invoker=None,
                       out_dir=tmp_path, args=args)


def _read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def test_motion_accuracy_dryrun(tmp_path):
    ctx = _ctx(tmp_path, {"reps": "3", "steps": "50", "modes": "none,hysteresis",
                          "axes": "xy", "settle_ms": "0", "frame_wait_s": "2"})
    path = motion_accuracy.run(ctx)
    assert path is not None and path.exists()
    rows = _read(path)
    trials = [r for r in rows if r["row_type"] == "trial"]
    assert len(trials) == 3 * 1 * 2 * 2  # reps * steps * modes * axes
    assert any(r["row_type"] == "summary_mean" for r in rows)
    
    none_x = [r for r in trials if r["mode"] == "none" and r["axis"] == "X"]
    assert abs(float(none_x[0]["fwd_px"]) - 10.0) <= 1.5


def test_stage_scale_dryrun(tmp_path):
    ctx = _ctx(tmp_path, {"reps": "5", "steps": "100", "axes": "xy",
                          "settle_ms": "0", "frame_wait_s": "2"})
    path = stage_scale.run(ctx)
    assert path is not None and path.exists()
    rows = _read(path)
    means = [r for r in rows if r["row_type"] == "summary_mean"]
    assert len(means) == 2  # X and Y
    
    for r in means:
        assert abs(float(r["um_per_step"]) - 0.1) <= 0.02
