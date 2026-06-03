"""Driver package. Hardware abstraction with real/mock pairs."""

import os
from typing import Callable, TypeVar

from retroscope.platform import is_pi

T = TypeVar("T")

def make_driver(real: Callable[[], T], mock: Callable[[], T]) -> T:
    """Return 'mock()' non-Pi or when forced. 'real()' on Pi.

    'MICROSCOPE_FORCE_MOCK=1' env var forces mocks across all drivers.
    """
    if os.environ.get("MICROSCOPE_FORCE_MOCK") == "1":
        return mock()
    return real() if is_pi() else mock()
