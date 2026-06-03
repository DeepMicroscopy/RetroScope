"""Platform detection real vs mock"""

import functools
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
