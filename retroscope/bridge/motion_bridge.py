"""Motion bridge: Exposes motor position to QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.motion_controller import JoystickAxisNormalizer


class MotionBridge(QObject):
    position_changed = Signal(int, int, int)
    motion_blocked = Signal(str)    # endstop, soft_limit_stage, etc.
    softLimitsChanged = Signal()
    stageLimitWizardChanged = Signal()
    z_move_requested = Signal(int)
    xy_move_requested = Signal(int, int)
    motors_deenergize_requested = Signal()
    joystick_cal_requested = Signal()
    joystickCalDone = Signal()
    joystick_center_changed = Signal()
    joystickAxisChanged = Signal()
    deadzone_set_requested = Signal(float)
    deadzoneChanged = Signal()

    def __init__(self, motion_controller=None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._motion_controller = motion_controller
        self._x = 0
        self._y = 0
        self._z = 0
        self._joy_cx: float = 0.0
        self._joy_cy: float = 0.0
        self._joy_center_valid = False
        self._joy_nx: float = 0.0
        self._joy_ny: float = 0.0
        self._joy_norm_x = JoystickAxisNormalizer()
        self._joy_norm_y = JoystickAxisNormalizer()
        self._joy_swap_xy = False
        self._joy_invert_x = False
        self._joy_invert_y = False
        self._deadzone: float = 0.05
        self._stage_limit_wizard_active = False
        self._stage_limit_wizard_step = 0
        if self._motion_controller is not None:
            self._motion_controller.soft_limits_changed.connect(self.softLimitsChanged)

    @Slot(int, int, int)
    def on_position_updated(self, x: int, y: int, z: int) -> None:
        self._x, self._y, self._z = x, y, z
        self.position_changed.emit(x, y, z)

    @Property(int, notify=position_changed)
    def posX(self) -> int:
        return self._x

    @Property(int, notify=position_changed)
    def posY(self) -> int:
        return self._y

    @Property(int, notify=position_changed)
    def posZ(self) -> int:
        return self._z

    @Property(bool, notify=softLimitsChanged)
    def softLimitsEnabled(self) -> bool:
        return bool(self._motion_controller and self._motion_controller.soft_limits_enabled)

    @Property(bool, notify=softLimitsChanged)
    def softLimitsCalibrated(self) -> bool:
        return bool(self._motion_controller and self._motion_controller.soft_limits_calibrated)

    @Property(int, notify=softLimitsChanged)
    def softLimitXMin(self) -> int:
        return int(self._motion_controller.soft_limit_x_min) if self._motion_controller else 0

    @Property(int, notify=softLimitsChanged)
    def softLimitXMax(self) -> int:
        return int(self._motion_controller.soft_limit_x_max) if self._motion_controller else 0

    @Property(int, notify=softLimitsChanged)
    def softLimitYMin(self) -> int:
        return int(self._motion_controller.soft_limit_y_min) if self._motion_controller else 0

    @Property(int, notify=softLimitsChanged)
    def softLimitYMax(self) -> int:
        return int(self._motion_controller.soft_limit_y_max) if self._motion_controller else 0

    @Property(bool, notify=stageLimitWizardChanged)
    def stageLimitWizardActive(self) -> bool:
        return self._stage_limit_wizard_active

    @Property(int, notify=stageLimitWizardChanged)
    def stageLimitWizardStep(self) -> int:
        return self._stage_limit_wizard_step

    @Slot()
    def startStageLimitWizard(self) -> None:
        self._stage_limit_wizard_active = True
        self._stage_limit_wizard_step = 0
        self.stageLimitWizardChanged.emit()

    @Slot()
    def closeStageLimitWizard(self) -> None:
        if not self._stage_limit_wizard_active:
            return
        self._stage_limit_wizard_active = False
        self.stageLimitWizardChanged.emit()

    @Slot(int)
    def setStageLimitWizardStep(self, step: int) -> None:
        step = max(0, min(3, int(step)))
        if step == self._stage_limit_wizard_step:
            return
        self._stage_limit_wizard_step = step
        self.stageLimitWizardChanged.emit()

    @Slot(result=bool)
    def confirmHomeZero(self) -> bool:
        if self._motion_controller is None:
            self.motion_blocked.emit("stage_home_failed")
            return False
        ok = bool(self._motion_controller.confirm_home_zero())
        if ok:
            self._stage_limit_wizard_step = 2
            self.stageLimitWizardChanged.emit()
        return ok

    @Slot(result=bool)
    def saveBottomRightLimit(self) -> bool:
        if self._motion_controller is None:
            self.motion_blocked.emit("soft_limits_invalid")
            return False
        ok = bool(self._motion_controller.save_bottom_right_limit())
        if ok:
            self._stage_limit_wizard_step = 3
            self.stageLimitWizardChanged.emit()
        return ok

    @Slot(bool)
    def setSoftLimitsEnabled(self, enabled: bool) -> None:
        if self._motion_controller is not None:
            self._motion_controller.set_soft_limits_enabled(enabled)

    @Slot()
    def clearSoftLimits(self) -> None:
        if self._motion_controller is not None:
            self._motion_controller.clear_soft_limits()

    @Slot(int)
    def moveZ_rel(self, steps: int) -> None:
        self.z_move_requested.emit(steps)

    @Slot(int, int)
    def moveRelXY(self, dx: int, dy: int) -> None:
        self.xy_move_requested.emit(dx, dy)

    @Slot()
    def deenergizeMotors(self) -> None:
        self.motors_deenergize_requested.emit()

    @Slot(float, float)
    def on_joystick_center_updated(self, cx: float, cy: float) -> None:
        self._joy_cx = cx
        self._joy_cy = cy
        self._joy_center_valid = True
        self._joy_norm_x.set_center(cx)
        self._joy_norm_y.set_center(cy)
        self.joystick_center_changed.emit()

    @Property(float, notify=joystick_center_changed)
    def joystickCenterX(self) -> float:
        return self._joy_cx

    @Property(float, notify=joystick_center_changed)
    def joystickCenterY(self) -> float:
        return self._joy_cy

    @Slot(int, int)
    def on_joystick_axes(self, x_raw: int, y_raw: int) -> None:
        x_axis, y_axis = self._map_joystick_raw_axes(x_raw, y_raw)
        nx = self._joy_norm_x.normalize(x_axis) if self._joy_center_valid else 0.0
        ny = self._joy_norm_y.normalize(y_axis) if self._joy_center_valid else 0.0
        if self._joy_invert_x:
            nx = -nx
        if self._joy_invert_y:
            ny = -ny
        self._joy_nx = nx
        self._joy_ny = ny
        self.joystickAxisChanged.emit()

    @Property(float, notify=joystickAxisChanged)
    def joystickNormX(self) -> float:
        return self._joy_nx

    @Property(float, notify=joystickAxisChanged)
    def joystickNormY(self) -> float:
        return self._joy_ny

    @Slot()
    def startJoystickCal(self) -> None:
        self._joy_center_valid = False
        self._joy_norm_x.set_center(None)
        self._joy_norm_y.set_center(None)
        self.joystick_cal_requested.emit()

    @Slot(bool)
    def setJoystickSwapXY(self, enabled: bool) -> None:
        self._joy_swap_xy = bool(enabled)
        self._joy_norm_x.set_center(self._joy_cx if self._joy_center_valid else None)
        self._joy_norm_y.set_center(self._joy_cy if self._joy_center_valid else None)

    @Slot(bool)
    def setJoystickInvertX(self, enabled: bool) -> None:
        self._joy_invert_x = bool(enabled)

    @Slot(bool)
    def setJoystickInvertY(self, enabled: bool) -> None:
        self._joy_invert_y = bool(enabled)

    def _map_joystick_raw_axes(self, x_raw: int, y_raw: int) -> tuple[int, int]:
        if self._joy_swap_xy:
            return int(y_raw), int(x_raw)
        return int(x_raw), int(y_raw)

    @Property(float, notify=deadzoneChanged)
    def deadzone(self) -> float:
        return self._deadzone

    @Slot(float)
    def setDeadzone(self, value: float) -> None:
        self._deadzone = value
        self.deadzone_set_requested.emit(value)
        self.deadzoneChanged.emit()

    @Slot(float)
    def on_deadzone_updated(self, value: float) -> None:
        self._deadzone = value
        self.deadzoneChanged.emit()
