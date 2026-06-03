"""Runtime lifecycle helpers for shortcuts, shutdown..."""

from __future__ import annotations

import sys

from retroscope.app.containers import Drivers, Services
from retroscope.app.drivers import stop_drivers
from retroscope.platform import is_pi

def install_keyboard_shortcuts(app, services: Services, drivers: Drivers) -> None:
    """Install development keyboard shortcuts when hardware buttons are absent."""
    if is_pi():
        return
    services.input_mgr.install_keyboard_shortcuts(
        app,
        buttons_driver=drivers.buttons,
        endstop_driver=drivers.endstop,
    )

def shutdown_and_exit(drivers: Drivers, config, exit_code: int) -> None:
    """Stop drivers, persist config and terminate with the passed exit code."""
    stop_drivers(drivers)
    config.save()
    sys.exit(exit_code)
