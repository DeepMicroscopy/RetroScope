"""Input manager: Wires hardware inputs to motion controller."""

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from retroscope.services.motion_controller import MotionController

_KBD_AXIS_VALUE = 20000
_KBD_ENCODER_STEP = 1


class InputManager(QObject):
    """Connects ADS1115 and encoder signals to MotionController."""

    def __init__(
        self,
        ads_driver,
        encoder_driver,
        motion_controller: MotionController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ads = ads_driver
        self._encoder = encoder_driver
        self._mc = motion_controller

        ads_driver.axes_updated.connect(motion_controller.on_axes_updated)
        encoder_driver.stepped.connect(motion_controller.on_encoder_stepped)

    def install_keyboard_shortcuts(
        self,
        app: QApplication,
        buttons_driver=None,
        endstop_driver=None,
    ) -> None:
        """Install keyboard shortcuts for mock simulation (macOS dev mode only).

        WASD        joystick axes
        Space       joystick center (release)
        PgUp/PgDn   encoder step +-1
        1/2/3/4     button press 0–3
        E           simulate endstop triggered/released toggle
        """
        from PySide6.QtCore import Qt, QEvent

        _WASD = {
            Qt.Key.Key_W: (0,  _KBD_AXIS_VALUE),
            Qt.Key.Key_S: (0, -_KBD_AXIS_VALUE),
            Qt.Key.Key_A: (-_KBD_AXIS_VALUE, 0),
            Qt.Key.Key_D: ( _KBD_AXIS_VALUE, 0),
        }

        ads_ref = self._ads
        mc_ref  = self._mc

        class GlobalKeyListener(QObject):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.one_shot = {}
                self.endstop_state = False
                self._held: set = set()

            def _push_axes(self):
                ax, ay = 0, 0
                for k in self._held:
                    dx, dy = _WASD[k]
                    ax += dx
                    ay += dy
                ax = max(-32767, min(32767, ax))
                ay = max(-32767, min(32767, ay))
                ads_ref.inject_axes(ax, ay)
                if ax == 0 and ay == 0:
                    mc_ref.emergency_stop()

            def eventFilter(self, obj, event):
                t = event.type()
                if t not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                    return super().eventFilter(obj, event)
                if event.isAutoRepeat():
                    return False
                key = event.key()
                if t == QEvent.Type.KeyPress:
                    if key in _WASD:
                        self._held.add(key)
                        self._push_axes()
                        return True
                    if key == Qt.Key.Key_Space:
                        self._held.clear()
                        ads_ref.inject_axes(0, 0)
                        mc_ref.emergency_stop()
                        return True
                    if key in self.one_shot:
                        self.one_shot[key]()
                        return True
                elif t == QEvent.Type.KeyRelease:
                    if key in _WASD:
                        self._held.discard(key)
                        self._push_axes()
                        return True
                return super().eventFilter(obj, event)

        self._kbd_listener = GlobalKeyListener(self)

        def _setup(key, cb):
            self._kbd_listener.one_shot[key] = cb

        # Encoder
        _setup(Qt.Key.Key_PageUp, lambda: self._encoder.simulate_step(_KBD_ENCODER_STEP))
        _setup(Qt.Key.Key_PageDown, lambda: self._encoder.simulate_step(-_KBD_ENCODER_STEP))

        # Buttons
        if buttons_driver is not None:
            _setup(Qt.Key.Key_1, lambda: buttons_driver.simulate_press(0))
            _setup(Qt.Key.Key_2, lambda: buttons_driver.simulate_press(1))
            _setup(Qt.Key.Key_3, lambda: buttons_driver.simulate_press(2))
            _setup(Qt.Key.Key_4, lambda: buttons_driver.simulate_press(3))

        # Endstop toggle
        if endstop_driver is not None:
            def _toggle_endstop():
                self._kbd_listener.endstop_state = not self._kbd_listener.endstop_state
                endstop_driver.simulate_trigger(self._kbd_listener.endstop_state)
            _setup(Qt.Key.Key_E, _toggle_endstop)

        app.installEventFilter(self._kbd_listener)
