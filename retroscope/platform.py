"""Platform detection real vs mock"""

import functools
import os
import sys
from typing import Literal

@functools.cache
def get_platform() -> Literal["pi", "mac"]:
    """Return 'pi' if running on Raspberry Pi with hardware libs (requirements need to be installed first), else 'mac'."""
    if sys.platform != "linux":
        return "mac"
    try:
        import smbus2
        import gpiod
        return "pi"
    except ImportError:
        return "mac"

def is_pi() -> bool:
    return get_platform() == "pi"

def is_wayland() -> bool:
    """True on a Wayland session (env set by retroscope.service)."""
    qpa = os.environ.get("QT_QPA_PLATFORM", "").lower()
    if qpa:
        return "wayland" in qpa
    return bool(os.environ.get("WAYLAND_DISPLAY"))
