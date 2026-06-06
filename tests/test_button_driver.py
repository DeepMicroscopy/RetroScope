"""Tests for hardware button driver helpers."""

from __future__ import annotations

from retroscope.drivers.buttons import ButtonsDriver


def test_gpio_button_driver_confirms_active_low_press() -> None:
    class Lines:
        def __init__(self, value) -> None:
            self.value = value

        def get_value(self, _pin: int):
            return self.value

    driver = ButtonsDriver()
    try:
        assert driver._line_is_active_low(Lines(0), 13) is True
        assert driver._line_is_active_low(Lines(1), 13) is False
    finally:
        driver.request_stop()
