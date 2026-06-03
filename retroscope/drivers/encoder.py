"""Rotary encoder driver via gpiod. Only handles quadrature decode on PIN_A / PIN_B."""

from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.drivers import make_driver

# Hardware constants
GPIO_CHIP = "/dev/gpiochip0"
PIN_A = 17  # Encoder channel A
PIN_B = 27  # Encoder channel B

# Quadrature decode table: index = (prev_a << 3 | prev_b << 2 | curr_a << 1 | curr_b)
_QUAD_TABLE = [
     0, -1,  1,  0,
     1,  0,  0, -1,
    -1,  0,  0,  1,
     0,  1, -1,  0,
]


# Real driver
class EncoderDriver(QThread):
    """Reads quadrature encoder via gpiod edge events. Emits signed delta ticks."""

    stepped = Signal(int)  # signed delta ticks

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._running = True

    def simulate_step(self, delta: int) -> None:
        pass  # no function on real driver

    def request_stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            import gpiod
            from gpiod.line import Bias, Direction, Edge
        except ImportError:
            print("[encoder] gpiod not available")
            return

        try:
            chip = gpiod.Chip(GPIO_CHIP)
            lines = chip.request_lines(
                config={
                    PIN_A: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        edge_detection=Edge.BOTH,
                        bias=Bias.PULL_UP,
                    ),
                    PIN_B: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        edge_detection=Edge.BOTH,
                        bias=Bias.PULL_UP,
                    ),
                },
                consumer="microscope-encoder",
            )

            prev_a = int(lines.get_value(PIN_A).value)
            prev_b = int(lines.get_value(PIN_B).value)

            while self._running:
                if not lines.wait_edge_events(timeout=0.05):
                    continue
                for _event in lines.read_edge_events():
                    curr_a = int(lines.get_value(PIN_A).value)
                    curr_b = int(lines.get_value(PIN_B).value)
                    idx = (prev_a << 3) | (prev_b << 2) | (curr_a << 1) | curr_b
                    delta = _QUAD_TABLE[idx & 0xF]
                    if delta != 0:
                        self.stepped.emit(delta)
                    prev_a = curr_a
                    prev_b = curr_b

            lines.release()
            chip.close()
        except Exception as e:
            print(f"[encoder] failed: {e}")


# Mock driver
class MockEncoder(QObject):
    """Silent until simulate_step() called (via keyboard simulation)."""

    stepped = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Slot(int)
    def simulate_step(self, delta: int) -> None:
        self.stepped.emit(delta)

    def request_stop(self) -> None:
        pass

    def start(self) -> None:
        pass

    def wait(self, msecs: int = -1) -> bool:
        return True


# Factory
def create_encoder_driver(parent: QObject | None = None) -> EncoderDriver | MockEncoder:
    return make_driver(
        lambda: EncoderDriver(parent),
        lambda: MockEncoder(parent),
    )
