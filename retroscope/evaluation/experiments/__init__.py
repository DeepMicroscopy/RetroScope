"""Evaluation experiments: Each module exposes 'run(ctx) -> pathlib.Path'."""

from retroscope.evaluation.experiments import (
    calibration_repeat,
    motion_accuracy,
    stage_scale,
    workflow_reliability,
)

REGISTRY = {
    "motion_accuracy": motion_accuracy.run,
    "stage_scale": stage_scale.run,
    "calibration_repeat": calibration_repeat.run,
    "workflow_reliability": workflow_reliability.run,
}
