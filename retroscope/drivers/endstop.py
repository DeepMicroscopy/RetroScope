"""Endstop driver: Standalone GPIO pin for focus axis hard limit.

Intentionally separate from the encoder so that all sources of 
Z movement (encoder, UI, autofocus routine, focus stacker) are protected by the same signal.
"""

from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.drivers import make_driver

# Hardware constants
GPIO_CHIP = "/dev/gpiochip0"
PIN_ENDSTOP = 16


# Real driver
class EndstopDriver(QThread):
    """Monitors endstop GPIO pin via gpiod edge events."""

    triggered = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = True

    def simulate_trigger(self, triggered: bool) -> None:
        pass  # no function on real driver

    def request_stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            import gpiod
            from gpiod.line import Bias, Direction, Edge, Value
        except ImportError:
            print("[endstop] gpiod not available")
            return

        try:
            chip = gpiod.Chip(GPIO_CHIP)
            lines = chip.request_lines(
                config={
                    PIN_ENDSTOP: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        edge_detection=Edge.BOTH,
                        bias=Bias.PULL_UP,
                    ),
                },
                consumer="microscope-endstop",
            )

            initial = lines.get_value(PIN_ENDSTOP)
            self.triggered.emit(initial == Value.ACTIVE)

            while self._running:
                if not lines.wait_edge_events(timeout=0.05):
                    continue
                for event in lines.read_edge_events():
                    # Normally-closed wiring: rising edge means the circuit opened, so the endstop is now triggered.
                    is_triggered = event.event_type == gpiod.EdgeEvent.Type.RISING_EDGE
                    self.triggered.emit(is_triggered)

            lines.release()
            chip.close()
        except Exception as e:
            print(f"[endstop] failed: {e}")


# Mock driver
class MockEndstop(QObject):
    """Silent until simulate_trigger() called."""

    triggered = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Slot(bool)
    def simulate_trigger(self, triggered: bool) -> None:
        self.triggered.emit(triggered)

    def request_stop(self) -> None:
        pass

    def start(self) -> None:
        pass

    def wait(self, msecs: int = -1) -> bool:
        return True


# Factory
def create_endstop_driver(parent: QObject | None = None) -> EndstopDriver | MockEndstop:
    return make_driver(
        lambda: EndstopDriver(parent),
        lambda: MockEndstop(parent),
    )
