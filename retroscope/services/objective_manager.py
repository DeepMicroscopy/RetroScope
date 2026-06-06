"""Objective profile manager: Stores profiles for all objectives and tracks the active one."""

import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot

from retroscope.services.config_store import CONFIG_RESET_KEY, ConfigStore


OBJECTIVES = ["4x", "10x", "20x", "40x", "100x"]

_DEFAULT_NA = {
    "4x": 0.10,
    "10x": 0.25,
    "20x": 0.40,
    "40x": 0.65,
    "100x": 1.25,
}
_MAGNIFICATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*x\b", re.IGNORECASE)


@dataclass
class ObjectiveProfile:
    name: str               # internal slot key, never changes
    display_name: str       # user-editable label shown in UI
    numerical_aperture: float
    backlash_x: int
    backlash_y: int
    backlash_z: int
    um_per_pixel: float
    dof_steps: int
    focus_stack_step: int
    autofocus_range_steps: int


def _default_profile(name: str) -> ObjectiveProfile:
    """Fallback profile if config is missing."""
    mag = int(name.replace("x", ""))
    return ObjectiveProfile(
        name=name,
        display_name=name,
        numerical_aperture=_DEFAULT_NA.get(name, 0.25),
        backlash_x=0,
        backlash_y=0,
        backlash_z=0,
        um_per_pixel=10.0 / mag,
        dof_steps=max(1, 100 // mag),
        focus_stack_step=max(1, 20 // mag),
        autofocus_range_steps=max(200, (100 // mag) * 10),
    )


def parse_magnification(label: str, fallback: str | None = None) -> float:
    """Return the first magnification in label, falling back to slot."""
    match = _MAGNIFICATION_RE.search(str(label or ""))
    if match:
        value = float(match.group(1))
        if value > 0:
            return value
    if fallback is not None and fallback != label:
        return parse_magnification(fallback)
    return 1.0


def _focus_stack_step_for_dof(dof_steps: int) -> int:
    return max(1, int(round(max(1, int(dof_steps)) / 2.0)))


def _autofocus_range_for_dof(dof_steps: int) -> int:
    return max(200, max(1, int(dof_steps)) * 10)


class ObjectiveManager(QObject):
    """Manages objective profiles and tracks the currently selected lens."""

    objective_changed = Signal(str) 
    names_changed     = Signal()

    def __init__(self, config: ConfigStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._active = "4x"
        self._profiles: dict[str, ObjectiveProfile] = {}
        self._load_profiles()
        if hasattr(config, "config_changed"):
            config.config_changed.connect(self._on_config_changed)

    def _load_profiles(self) -> None:
        self._profiles = {}
        for name in OBJECTIVES:
            key = f"objectives.{name}"
            data = self._config.get(key, {})

            dof_steps = int(data.get("dof_steps", data.get("dof_um", _default_profile(name).dof_steps)))
            self._profiles[name] = ObjectiveProfile(
                name=name,
                display_name=data.get("display_name", name),
                numerical_aperture=float(data.get("numerical_aperture", _default_profile(name).numerical_aperture)),
                backlash_x=int(data.get("backlash_x", 0)),
                backlash_y=int(data.get("backlash_y", 0)),
                backlash_z=data.get("backlash_z", 0),
                um_per_pixel=data.get("um_per_pixel", _default_profile(name).um_per_pixel),
                dof_steps=dof_steps,
                focus_stack_step=data.get("focus_stack_step", _default_profile(name).focus_stack_step),
                autofocus_range_steps=int(data.get("autofocus_range_steps", max(200, dof_steps * 10))),
            )
        # Restore last-used objective from config
        saved = self._config.get("ui.active_objective", "4x")
        if saved in OBJECTIVES:
            self._active = saved

    def _on_config_changed(self, key: str) -> None:
        if key != CONFIG_RESET_KEY:
            return
        self._load_profiles()
        self.names_changed.emit()
        self.objective_changed.emit(self._active)

    @property
    def active_objective(self) -> str:
        return self._active

    def current_profile(self) -> ObjectiveProfile:
        return self._profiles[self._active]

    def profile(self, name: str) -> ObjectiveProfile:
        return self._profiles.get(name, _default_profile(name))

    @Slot(str)
    def set_active(self, name: str) -> None:
        if name not in OBJECTIVES:
            return
        if name == self._active:
            return
        self._active = name
        self._config.set("ui.active_objective", name)
        self.objective_changed.emit(name)

    def display_names(self) -> list[str]:
        """Return the list of display names in OBJECTIVES order."""
        return [self._profiles[n].display_name for n in OBJECTIVES]

    def set_display_name(self, slot: str, name: str) -> None:
        """Rename the UI label of an objective slot (does not change the slot key)."""
        if slot not in OBJECTIVES:
            return
        name = name.strip()
        if not name:
            return
        if self._profiles[slot].display_name == name:
            return
        self._profiles[slot].display_name = name
        self._config.set(f"objectives.{slot}.display_name", name)
        self.names_changed.emit()

    _SETTABLE_PARAMS = {
        "numerical_aperture",
        "backlash_x", "backlash_y", "backlash_z",
        "um_per_pixel", "dof_steps", "focus_stack_step", "autofocus_range_steps",
    }

    def set_param(self, name: str, param: str, value) -> None:
        """Update a single profile parameter and persist to config."""
        if name not in OBJECTIVES:
            return
        if param not in self._SETTABLE_PARAMS:
            return
        profile = self._profiles[name]
        if getattr(profile, param) == value:
            return
        # Apply to in-memory profile
        setattr(profile, param, value)
        # Persist
        self._config.set(f"objectives.{name}.{param}", value)
        # If this is the active objective, notify listeners
        if name == self._active:
            self.objective_changed.emit(name)

    def magnification_for(self, name: str) -> float:
        profile = self.profile(name)
        return parse_magnification(profile.display_name, profile.name)

    def apply_scaled_um_per_pixel(self, base_name: str, base_um_per_pixel: float) -> None:
        """Save measured scale on base objective and derive all other scales."""
        if base_name not in OBJECTIVES:
            return
        base_scale = max(0.001, float(base_um_per_pixel))
        base_mag = max(0.001, self.magnification_for(base_name))
        for name in OBJECTIVES:
            target_mag = max(0.001, self.magnification_for(name))
            self._set_param_silent(name, "um_per_pixel", base_scale * base_mag / target_mag)
        self.objective_changed.emit(self._active)

    def apply_scaled_dof_steps(self, base_name: str, base_dof_steps: int) -> None:
        """Save measured DoF on base objective and derive focus parameters by NA."""
        if base_name not in OBJECTIVES:
            return
        base_dof = max(1, int(base_dof_steps))
        base_na = self._safe_na(base_name)
        for name in OBJECTIVES:
            target_na = self._safe_na(name)
            dof_steps = max(1, int(round(base_dof * (base_na / target_na) ** 2)))
            self._set_param_silent(name, "dof_steps", dof_steps)
            self._set_param_silent(name, "focus_stack_step", _focus_stack_step_for_dof(dof_steps))
            self._set_param_silent(name, "autofocus_range_steps", _autofocus_range_for_dof(dof_steps))
        self.objective_changed.emit(self._active)

    def apply_scaled_focus_stack_step(self, base_name: str, base_focus_stack_step: int) -> None:
        """Apply a user-tuned stack-step ratio from the base objective to all profiles."""
        if base_name not in OBJECTIVES:
            return
        base_profile = self.profile(base_name)
        base_dof = max(1, int(base_profile.dof_steps))
        ratio = max(1, int(base_focus_stack_step)) / base_dof
        for name in OBJECTIVES:
            profile = self.profile(name)
            focus_stack_step = max(1, int(round(max(1, int(profile.dof_steps)) * ratio)))
            self._set_param_silent(name, "focus_stack_step", focus_stack_step)
        self.objective_changed.emit(self._active)

    def apply_backlash_axis_to_all(self, axis: str, value: int) -> None:
        clean_axis = str(axis).lower()
        if clean_axis not in {"x", "y", "z"}:
            return
        clean = max(0, int(value))
        param = f"backlash_{clean_axis}"
        for name in OBJECTIVES:
            self._set_param_silent(name, param, clean)
        self.objective_changed.emit(self._active)

    def _set_param_silent(self, name: str, param: str, value) -> None:
        if name not in OBJECTIVES or param not in self._SETTABLE_PARAMS:
            return
        setattr(self._profiles[name], param, value)
        self._config.set(f"objectives.{name}.{param}", value)

    def _safe_na(self, name: str) -> float:
        return max(0.01, float(self.profile(name).numerical_aperture))
