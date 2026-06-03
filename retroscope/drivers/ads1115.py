"""ADS1115 joystick ADC driver."""

import threading
import time

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from retroscope.drivers import make_driver

# Hardware constants
I2C_BUS = 1
I2C_ADDR = 0x48
POLL_HZ = 100

# ADS1115 registers & config masks
_REG_CONV = 0x00
_REG_CONFIG = 0x01
_CONFIG_CH0 = 0xC183
_CONFIG_CH1 = 0xD183
_CONFIG_OS_START = 0x8000

def _read_channel(bus, addr: int, channel: int) -> int:
    """Trigger single-shot conversion and return signed 16-bit result."""
    cfg = _CONFIG_CH0 if channel == 0 else _CONFIG_CH1
    cfg |= _CONFIG_OS_START
    hi = (cfg >> 8) & 0xFF
    lo = cfg & 0xFF
    bus.write_i2c_block_data(addr, _REG_CONFIG, [hi, lo])
    time.sleep(0.009)
    raw = bus.read_i2c_block_data(addr, _REG_CONV, 2)
    value = (raw[0] << 8) | raw[1]
    if value >= 0x8000:
        value -= 0x10000
    return value


# Real driver
class ADS1115Driver(QThread):
    """Polls ADS1115 at POLL_HZ and emits axes_updated."""

    axes_updated = Signal(int, int)

    def __init__(self, i2c_lock: threading.Lock, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._i2c_lock = i2c_lock
        self._running = True

    def inject_axes(self, x: int, y: int) -> None:
        """No function on real driver, only used by mock."""
        pass

    def request_stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            import smbus2
        except ImportError:
            print("[ads1115] smbus2 not available")
            return

        interval = 1.0 / POLL_HZ
        last_error_t = 0.0
        try:
            with smbus2.SMBus(I2C_BUS) as bus:
                while self._running:
                    t0 = time.monotonic()
                    try:
                        with self._i2c_lock:
                            x = _read_channel(bus, I2C_ADDR, 0)
                            y = _read_channel(bus, I2C_ADDR, 1)
                        self.axes_updated.emit(x, y)
                    except Exception as e:
                        now = time.monotonic()
                        if now - last_error_t >= 2.0:
                            print(f"[ads1115] read failed: {e}")
                            last_error_t = now
                    elapsed = time.monotonic() - t0
                    remaining = interval - elapsed
                    if remaining > 0:
                        time.sleep(remaining)
        except Exception as e:
            print(f"[ads1115] worker failed: {e}")


# Mock driver
class MockADS1115(QObject):
    """Emits (0, 0) until inject_axes() is called (via keyboard simulation)."""

    axes_updated = Signal(int, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._x = 0
        self._y = 0
        self._timer = QTimer(self)
        self._timer.setInterval(10)  # 100 Hz
        self._timer.timeout.connect(self._emit)

    @Slot(int, int)
    def inject_axes(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    def request_stop(self) -> None:
        self._timer.stop()

    def start(self) -> None:
        self._timer.start()

    def wait(self, msecs: int = -1) -> bool:
        return True

    def _emit(self) -> None:
        self.axes_updated.emit(self._x, self._y)


# Factory
def create_ads_driver(
    i2c_lock: threading.Lock, parent: QObject | None = None
) -> ADS1115Driver | MockADS1115:
    return make_driver(
        lambda: ADS1115Driver(i2c_lock, parent),
        lambda: MockADS1115(parent),
    )
