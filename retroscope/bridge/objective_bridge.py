"""Objective bridge: Exposes active objective and profile data to QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.objective_manager import OBJECTIVES, ObjectiveManager


class ObjectiveBridge(QObject):
    objective_changed = Signal(str)
    params_changed    = Signal()
    names_changed     = Signal()

    def __init__(self, manager: ObjectiveManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mgr = manager
        manager.objective_changed.connect(self._on_changed)
        manager.names_changed.connect(self.names_changed)

    def _on_changed(self, name: str) -> None:
        self.objective_changed.emit(name)
        self.params_changed.emit()
        self.names_changed.emit()   # activeDisplayName depends on active objective too

    @Property(str, notify=objective_changed)
    def activeObjective(self) -> str:
        return self._mgr.active_objective

    @Property(str, notify=names_changed)
    def activeDisplayName(self) -> str:
        return self._mgr.current_profile().display_name

    @Property(list, constant=True)
    def objectiveNames(self) -> list:
        return list(OBJECTIVES)

    @Property(list, notify=names_changed)
    def objectiveDisplayNames(self) -> list:
        return self._mgr.display_names()

    @Slot(str, str)
    def renameObjective(self, slot: str, name: str) -> None:
        self._mgr.set_display_name(slot, name)

    @Property(float, notify=params_changed)
    def activeNumericalAperture(self) -> float:
        return self._mgr.current_profile().numerical_aperture

    @Slot(float)
    def setNumericalAperture(self, v: float) -> None:
        self._mgr.set_param(self._mgr.active_objective, "numerical_aperture", max(0.01, float(v)))

    @Slot(str, float)
    def setNumericalApertureFor(self, slot: str, v: float) -> None:
        self._mgr.set_param(slot, "numerical_aperture", max(0.01, float(v)))

    @Property(float, notify=objective_changed)
    def umPerPixel(self) -> float:
        return self._mgr.current_profile().um_per_pixel

    @Property(float, notify=objective_changed)
    def scaleBarUm(self) -> float:
        # Returns a "round" scale bar length in µm for the default 100px bar
        px = 100
        raw_um = px * self._mgr.current_profile().um_per_pixel
        # Snap to nearest "round" value
        for nice in [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000]:
            if nice >= raw_um * 0.5:
                return float(nice)
        return float(raw_um)

    @Slot(str)
    def select(self, name: str) -> None:
        self._mgr.set_active(name)


    # Active objective motion parameters (notify params_changed)
    @Property(int, notify=params_changed)
    def activeBacklashX(self) -> int:
        return int(self._mgr.current_profile().backlash_x)

    @Slot(int)
    def setBacklashX(self, v: int) -> None:
        self._mgr.apply_backlash_axis_to_all("x", max(0, int(v)))

    @Property(int, notify=params_changed)
    def activeBacklashY(self) -> int:
        return int(self._mgr.current_profile().backlash_y)

    @Slot(int)
    def setBacklashY(self, v: int) -> None:
        self._mgr.apply_backlash_axis_to_all("y", max(0, int(v)))

    @Property(int, notify=params_changed)
    def activeBacklashZ(self) -> int:
        return int(self._mgr.current_profile().backlash_z)

    @Slot(int)
    def setBacklashZ(self, v: int) -> None:
        self._mgr.apply_backlash_axis_to_all("z", max(0, int(v)))


    # Scale & Focus
    @Property(float, notify=params_changed)
    def activeUmPerPixel(self) -> float:
        return self._mgr.current_profile().um_per_pixel

    @Slot(float)
    def setUmPerPixel(self, v: float) -> None:
        self._mgr.apply_scaled_um_per_pixel(self._mgr.active_objective, max(0.001, v))

    @Property(int, notify=params_changed)
    def activeDofSteps(self) -> int:
        return self._mgr.current_profile().dof_steps

    @Slot(int)
    def setDofSteps(self, v: int) -> None:
        self._mgr.apply_scaled_dof_steps(self._mgr.active_objective, max(1, int(v)))

    @Property(int, notify=params_changed)
    def activeFocusStackStep(self) -> int:
        return self._mgr.current_profile().focus_stack_step

    @Slot(int)
    def setFocusStackStep(self, v: int) -> None:
        self._mgr.apply_scaled_focus_stack_step(self._mgr.active_objective, max(1, v))

    @Property(int, notify=params_changed)
    def activeAutofocusRangeSteps(self) -> int:
        profile = self._mgr.current_profile()
        return int(getattr(profile, "autofocus_range_steps", max(200, profile.dof_steps * 10)))

    @Slot(int)
    def setAutofocusRangeSteps(self, v: int) -> None:
        self._mgr.set_param(self._mgr.active_objective, "autofocus_range_steps", max(50, int(v)))


    # Stage
    @Property(float, notify=params_changed)
    def stageUmPerStepX(self) -> float:
        return float(self._mgr._config.get("motor.stage_um_per_step_x", 0.0))

    @Property(float, notify=params_changed)
    def stageUmPerStepY(self) -> float:
        return float(self._mgr._config.get("motor.stage_um_per_step_y", 0.0))

    @Slot(float, float)
    def setStageUmPerStep(self, x: float, y: float) -> None:
        self._mgr._config.set("motor.stage_um_per_step_x", max(0.0, float(x)))
        self._mgr._config.set("motor.stage_um_per_step_y", max(0.0, float(y)))
        self.params_changed.emit()

    @Slot()
    def resetActiveToDefaults(self) -> None:
        self._mgr.reset_to_defaults(self._mgr.active_objective)
