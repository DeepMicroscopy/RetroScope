"""Evaluation runner: executes one experiment in a worker thread against the live
services, then quits the application."""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QThread

from retroscope.evaluation.context import EvalContext
from retroscope.evaluation.experiments import REGISTRY
from retroscope.evaluation.service_drive import MainThreadInvoker


def parse_eval_args(pairs: list[str] | None) -> dict:
    out: dict = {}
    for item in pairs or []:
        if "=" in item:
            k, v = item.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class EvaluationRunner(QThread):
    """Runs a single named experiment, then quits app."""

    def __init__(self, app, services, sangaboard, experiment: str,
                 args: dict, out_dir: str | Path, parent=None) -> None:
        super().__init__(parent)
        self._app = app
        self._experiment = experiment
        self._invoker = MainThreadInvoker()
        self._ctx = EvalContext(
            services=services, sangaboard=sangaboard, invoker=self._invoker,
            out_dir=Path(out_dir), args=args,
        )

    def _set_motion_lock(self, locked: bool) -> None:
        mc = getattr(self._ctx.services, "motion_ctrl", None)
        if mc is not None and hasattr(mc, "set_external_motion_lock"):
            self._invoker.call_sync(lambda: mc.set_external_motion_lock(locked))

    def run(self) -> None:  # executes in the worker thread
        try:
            fn = REGISTRY.get(self._experiment)
            if fn is None:
                print(f"[eval] unknown experiment '{self._experiment}'. "
                      f"Choices: {', '.join(sorted(REGISTRY))}")
            else:
                print(f"[eval] starting '{self._experiment}' with args {self._ctx.args}")
                # Suppress manual joystick/encoder motion so it does not compete with the experiment for the serial line.
                self._set_motion_lock(True)
                try:
                    fn(self._ctx)
                finally:
                    self._set_motion_lock(False)
                print(f"[eval] '{self._experiment}' done.")
        except Exception:
            traceback.print_exc()
        finally:
            self._invoker.call(self._app.quit)
