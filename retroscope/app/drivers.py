"""Driver construction and lifecycle."""

from __future__ import annotations

import threading

from retroscope.app.containers import Drivers
from retroscope.platform import is_pi

def create_drivers() -> Drivers:
    """Create all hardware or mock drivers."""
    from retroscope.drivers.ads1115 import create_ads_driver
    from retroscope.drivers.buttons import create_buttons_driver
    from retroscope.drivers.encoder import create_encoder_driver
    from retroscope.drivers.endstop import create_endstop_driver
    from retroscope.drivers.sangaboard import create_sangaboard_driver

    i2c_lock = threading.Lock()
    return Drivers(
        sangaboard=create_sangaboard_driver(),
        ads=create_ads_driver(i2c_lock),
        encoder=create_encoder_driver(),
        endstop=create_endstop_driver(),
        buttons=create_buttons_driver(),
    )

def start_drivers(drivers: Drivers) -> None:
    """Start hardware threads."""
    drivers.sangaboard.start()

    if is_pi():
        drivers.ads.start()
        drivers.encoder.start()
        drivers.endstop.start()
        drivers.buttons.start()
    else:
        drivers.ads.start()

def stop_drivers(drivers: Drivers) -> None:
    """Gracefuly stop hardware threads in reverse startup order."""
    if is_pi():
        drivers.buttons.request_stop()
        drivers.buttons.wait(1000)
        drivers.endstop.request_stop()
        drivers.endstop.wait(1000)
        drivers.encoder.request_stop()
        drivers.encoder.wait(2000)
        drivers.ads.request_stop()
        drivers.ads.wait(1000)
    else:
        drivers.buttons.request_stop()
        drivers.endstop.request_stop()
        drivers.encoder.request_stop()
        drivers.ads.request_stop()

    drivers.sangaboard.request_stop()
    drivers.sangaboard.wait(3000)
