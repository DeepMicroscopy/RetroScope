"""Calibration bridge for stage and backlash workflows."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.backlash_measurement import center_crop, measure_offset
from retroscope.services.stage_calibration import stage_um_per_step


class CalibrationBridge(QObject):
    stage_scale_changed = Signal()
    backlash_measurement_changed = Signal()

    def __init__(self, camera_svc, motion_ctrl, objective_mgr, config, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._camera = camera_svc
        self._motion = motion_ctrl
        self._obj = objective_mgr
        self._config = config
        self._backlash_reference = None
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._match_score = 0.0
        self._last_axis = "x"
        self._reverse_steps = 0

    @Property(float, notify=stage_scale_changed)
    def stageUmPerStepX(self) -> float:
        return float(self._config.get("motor.stage_um_per_step_x", 0.0))

    @Property(float, notify=stage_scale_changed)
    def stageUmPerStepY(self) -> float:
        return float(self._config.get("motor.stage_um_per_step_y", 0.0))

    @Slot(str, int, float, result=bool)
    def setStageAxisCalibration(self, axis: str, motor_steps: int, observed_pixels: float) -> bool:
        return self.setStageAxisCalibrationWithScale(
            axis,
            motor_steps,
            observed_pixels,
            self._obj.current_profile().um_per_pixel,
        )

    @Slot(str, int, float, float, result=bool)
    def setStageAxisCalibrationWithScale(
        self,
        axis: str,
        motor_steps: int,
        observed_pixels: float,
        um_per_pixel: float,
    ) -> bool:
        value = stage_um_per_step(
            observed_pixels,
            um_per_pixel,
            motor_steps,
        )
        return self._set_stage_axis_value(axis, value)

    def _set_stage_axis_value(self, axis: str, value: float) -> bool:
        if value <= 0.0:
            return False
        clean_axis = str(axis).lower()
        if clean_axis == "x":
            self._config.set("motor.stage_um_per_step_x", value)
        elif clean_axis == "y":
            self._config.set("motor.stage_um_per_step_y", value)
        else:
            return False
        self.stage_scale_changed.emit()
        return True

    @Property(float, notify=backlash_measurement_changed)
    def backlashOffsetXPx(self) -> float:
        return self._offset_x

    @Property(float, notify=backlash_measurement_changed)
    def backlashOffsetYPx(self) -> float:
        return self._offset_y

    @Property(float, notify=backlash_measurement_changed)
    def backlashMatchScore(self) -> float:
        return self._match_score

    @Property(int, notify=backlash_measurement_changed)
    def backlashReverseSteps(self) -> int:
        return self._reverse_steps

    @Slot(result=bool)
    def setBacklashReference(self) -> bool:
        frame = self._camera.get_latest_frame()
        crop = center_crop(frame, 96)
        if crop is None:
            return False
        self._backlash_reference = crop
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._match_score = 1.0
        self._reverse_steps = 0
        self.backlash_measurement_changed.emit()
        return True

    @Slot(str)
    def beginBacklashMeasurement(self, axis: str) -> None:
        clean_axis = str(axis).lower()
        if clean_axis in {"x", "y", "z"}:
            self._last_axis = clean_axis
        self._reverse_steps = 0
        self.backlash_measurement_changed.emit()

    @Slot(bool)
    def setDofCalibrationActive(self, active: bool) -> None:
        """Toggle the fixed fine Z-encoder step used during DoF calibration."""
        self._motion.set_calibration_encoder_step_active(active)

    @Slot(str, int, result=bool)
    def jogStageAxis(self, axis: str, steps: int) -> bool:
        clean_axis = str(axis).lower()
        amount = int(steps)
        dx = amount if clean_axis == "x" else 0
        dy = amount if clean_axis == "y" else 0
        if dx == dy == 0:
            return False
        return bool(self._motion.calibration_move_rel(dx, dy, 0))

    @Slot(str, int, result=bool)
    def jogBacklashAxis(self, axis: str, steps: int) -> bool:
        clean_axis = str(axis).lower()
        amount = int(steps)
        dx = amount if clean_axis == "x" else 0
        dy = amount if clean_axis == "y" else 0
        dz = amount if clean_axis == "z" else 0
        if dx == dy == dz == 0:
            return False
        ok = bool(self._motion.calibration_move_rel(dx, dy, dz))
        if ok and clean_axis == self._last_axis:
            self._reverse_steps += abs(amount)
        return ok

    @Slot(result=bool)
    def measureBacklashOffset(self) -> bool:
        if self._backlash_reference is None:
            return False
        frame = self._camera.get_latest_frame()
        measured = measure_offset(self._backlash_reference, frame)
        if measured is None:
            return False
        self._offset_x = measured.dx_px
        self._offset_y = measured.dy_px
        self._match_score = measured.score
        self.backlash_measurement_changed.emit()
        return True

    @Slot(str, int, result=bool)
    def acceptBacklashSteps(self, axis: str, steps: int) -> bool:
        clean_axis = str(axis).lower()
        value = max(0, int(steps))
        if clean_axis == "x":
            self._obj.apply_backlash_axis_to_all("x", value)
        elif clean_axis == "y":
            self._obj.apply_backlash_axis_to_all("y", value)
        elif clean_axis == "z":
            self._obj.apply_backlash_axis_to_all("z", value)
        else:
            return False
        return True
