"""RetroScope Control Software entry point.

Start with ./deploy/start.sh for single-instance lock and auto-restart on exit code 42 (update/restart).
"""

from __future__ import annotations

import argparse

from retroscope.app.runner import run_application

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RetroScope Control Software")
    parser.add_argument("--dev", action="store_true", help="Enable QML hot reload")
    parser.add_argument("--mock", action="store_true", help="Force mock drivers")
    parser.add_argument("--scale", type=float, default=1.0, help="UI scale factor (e.g. 1.5, 2.0)")
    parser.add_argument("--eval", default=None,
                        help="Run an evaluation experiment then quit "
                             "(motion_accuracy, stage_scale, calibration_repeat, workflow_reliability)")
    parser.add_argument("--eval-arg", action="append", default=[], metavar="key=value",
                        help="Experiment parameter, repeatable (e.g. --eval-arg axes=xy --eval-arg reps=8)")
    parser.add_argument("--eval-out", default="evaluation_output",
                        help="Directory for evaluation CSV output")
    return parser.parse_args()

def main() -> None:
    run_application(parse_args())

if __name__ == "__main__":
    main()
