"""States used by SettingsBridge."""

from __future__ import annotations

from dataclasses import dataclass

from retroscope.platform import is_pi

def _clamped_int(value, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value)))

@dataclass
class InputSettingsState:
    deadzone_pct: int
    curve: str
    expo_strength: int
    swap_xy: bool
    invert_x: bool
    invert_y: bool
    joystick_smoothing_pct: int
    z_encoder_sensitivity_pct: int
    max_pan_speed_px_per_sec: int
    z_encoder_step_multiplier: float

    @classmethod
    def from_config(cls, config) -> "InputSettingsState":
        return cls(
            deadzone_pct=int(config.get("input.deadzone_pct", 8)),
            curve=str(config.get("input.curve", "exponential")),
            expo_strength=int(config.get("input.expo_strength", 70)),
            swap_xy=bool(config.get("input.swap_xy", is_pi())),
            invert_x=bool(config.get("input.invert_x", False)),
            invert_y=bool(config.get("input.invert_y", False)),
            joystick_smoothing_pct=_clamped_int(
                config.get("input.joystick_smoothing_pct", 25),
                0,
                100,
            ),
            z_encoder_sensitivity_pct=_clamped_int(
                config.get("input.z_encoder_sensitivity_pct", 100),
                25,
                400,
            ),
            max_pan_speed_px_per_sec=_clamped_int(
                config.get("input.max_pan_speed_px_per_sec", 400),
                10,
                4000,
            ),
            z_encoder_step_multiplier=float(config.get("input.z_encoder_step_multiplier", 1.0)),
        )

@dataclass
class CameraSettingsState:
    device: str
    resolution: str
    fps: int
    image_format: str
    naming_pattern: str

    @classmethod
    def from_config(cls, config) -> "CameraSettingsState":
        return cls(
            device=str(config.get("camera.device", "/dev/video0")),
            resolution=str(config.get("camera.resolution", "640x360")),
            fps=int(config.get("camera.fps", 8)),
            image_format=str(config.get("camera.image_format", "OME-TIFF")),
            naming_pattern=str(config.get("camera.naming_pattern", "{date}_{time}_{obj}")),
        )

@dataclass
class SystemSettingsState:
    restart_after_update: bool

    @classmethod
    def from_config(cls, config) -> "SystemSettingsState":
        return cls(
            restart_after_update=bool(config.get("system.restart_after_update", True)),
        )
