"""GPIO button driver: 4 physical buttons, active LOW with pull-up."""

import time

from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.drivers import make_driver

# Hardware constants
GPIO_CHIP = "/dev/gpiochip0"
BUTTON_PINS = [13, 6, 19, 26]
_PIN_TO_INDEX = {pin: i for i, pin in enumerate(BUTTON_PINS)}
# Without this guard a single tap fired button_pressed 2+ times, which flips toggle actions (e.g. autofocus start<->cancel).
_DEBOUNCE_S = 0.25
_PRESS_CONFIRM_S = 0.06
_NOISE_SUPPRESS_S = 1.5

# Real driver
class ButtonsDriver(QThread):
    """Monitors 4 GPIO buttons via gpiod edge events. Only emits on the falling edge (press), not release."""

    button_pressed = Signal(int)  # button index 0–3

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = True
        self._last_emit_t: dict[int, float] = {}
        self._noise_suppress_until = 0.0

    def simulate_press(self, index: int) -> None:
        pass  # no-op on real driver

    def request_stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            import gpiod
            from gpiod.line import Bias, Direction, Edge
        except ImportError:
            print("[buttons] gpiod not available")
            return

        try:
            chip = gpiod.Chip(GPIO_CHIP)
            lines = chip.request_lines(
                config={
                    pin: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        edge_detection=Edge.FALLING,   # press only (active LOW)
                        bias=Bias.PULL_UP,
                    )
                    for pin in BUTTON_PINS
                },
                consumer="microscope-buttons",
            )

            while self._running:
                if not lines.wait_edge_events(timeout=0.05):
                    continue
                events = lines.read_edge_events()
                now = time.monotonic()
                if len(events) > 1:
                    self._noise_suppress_until = now + _NOISE_SUPPRESS_S
                    continue
                for event in events:
                    idx = _PIN_TO_INDEX.get(event.line_offset)
                    if idx is None:
                        continue
                    if now < self._noise_suppress_until:
                        continue
                    last = self._last_emit_t.get(idx, 0.0)
                    if now - last < _DEBOUNCE_S:
                        continue
                    if not self._confirm_pressed(lines, event.line_offset):
                        self._noise_suppress_until = time.monotonic() + _NOISE_SUPPRESS_S
                        continue
                    self._last_emit_t[idx] = now
                    self.button_pressed.emit(idx)

            lines.release()
            chip.close()
        except Exception as e:
            print(f"[buttons] failed: {e}")

    def _confirm_pressed(self, lines, pin: int) -> bool:
        deadline = time.monotonic() + _PRESS_CONFIRM_S
        while self._running:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.01, remaining))
        if not self._running:
            return False
        return self._line_is_active_low(lines, pin)

    def _line_is_active_low(self, lines, pin: int) -> bool:
        try:
            value = lines.get_value(pin)
        except Exception:
            return True
        name = str(getattr(value, "name", "")).lower()
        if name:
            return "inactive" in name or name == "0"
        text = str(value).lower()
        if "inactive" in text:
            return True
        if "active" in text:
            return False
        try:
            return int(value) == 0
        except Exception:
            return False

# Mock driver: On macOS it exposes simulate_press(index) called by keyboard shortcuts (keys 1–4)
class MockButtons(QObject):
    """Silent until simulate_press(index) called."""

    button_pressed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Slot(int)
    def simulate_press(self, index: int) -> None:
        if 0 <= index <= 3:
            self.button_pressed.emit(index)

    def request_stop(self) -> None:
        pass

    def start(self) -> None:
        pass

    def wait(self, msecs: int = -1) -> bool:
        return True


# Factory
def create_buttons_driver(parent: QObject | None = None) -> ButtonsDriver | MockButtons:
    return make_driver(
        lambda: ButtonsDriver(parent),
        lambda: MockButtons(parent),
    )
