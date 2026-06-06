"""SettingsBridge: Exposes joystick, camera, storage and system settings to QML.

All settings are persisted to ConfigStore and loaded on startup.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.platform import is_pi
from retroscope.services.config_store import CONFIG_RESET_KEY

class SettingsBridge(QObject):
    # Joystick signals
    joystick_deadzone_changed  = Signal(int)
    joystick_curve_changed     = Signal(str)
    joystick_expo_changed      = Signal(int)
    joystick_swap_xy_changed   = Signal(bool)
    joystick_invert_x_changed  = Signal(bool)
    joystick_invert_y_changed  = Signal(bool)
    joystick_sensitivity_changed = Signal(int)
    z_encoder_sensitivity_changed = Signal(int)
    max_pan_speed_changed         = Signal(int)
    z_encoder_step_multiplier_changed = Signal(float)
    sangaboard_step_time_changed = Signal(int)
    sangaboard_ramp_time_changed = Signal(int)
    sangaboard_step_time_set_requested = Signal(int)
    sangaboard_ramp_time_set_requested = Signal(int)
    # Autofocus signals
    autofocus_speed_preset_changed       = Signal(str)
    autofocus_settle_ms_changed          = Signal(int)
    autofocus_move_start_ms_changed      = Signal(int)
    autofocus_coarse_positions_changed   = Signal(int)
    autofocus_fine_positions_changed     = Signal(int)
    autofocus_samples_per_position_changed = Signal(int)
    autofocus_min_confidence_changed     = Signal(float)
    # Camera signals
    camera_device_changed      = Signal(str)
    camera_resolution_changed  = Signal(str)
    camera_fps_changed         = Signal(int)
    camera_format_changed      = Signal(str)
    camera_naming_changed      = Signal(str)
    camera_frame_analysis_changed = Signal(bool)
    camera_live_video_changed     = Signal(bool)
    # Storage signals
    capture_root_changed       = Signal(str)
    storage_changed            = Signal()
    # System signals
    restart_after_update_changed = Signal(bool)

    def __init__(self, config, image_store, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._store  = image_store
        self._load_from_config()
        if hasattr(config, "config_changed"):
            config.config_changed.connect(self._on_config_changed)

    def _load_from_config(self) -> None:
        config = self._config
        # Joystick
        self._deadzone   = int(config.get("input.deadzone_pct", 8))
        self._curve      = str(config.get("input.curve", "exponential"))
        self._expo       = int(config.get("input.expo_strength", 70))
        self._sensitivity = int(config.get("input.sensitivity_pct", 100))
        self._swap_xy    = bool(config.get("input.swap_xy", is_pi()))
        self._invert_x   = bool(config.get("input.invert_x", False))
        self._invert_y   = bool(config.get("input.invert_y", False))
        self._z_encoder_sensitivity = max(25, min(400, int(config.get("input.z_encoder_sensitivity_pct", 100))))
        self._max_pan_speed = max(10, min(4000, int(config.get("input.max_pan_speed_px_per_sec", 400))))
        self._z_enc_mult    = max(0.25, min(4.0, float(config.get("input.z_encoder_step_multiplier", 1.0))))
        step_override = config.get("motor.sangaboard_step_time_us", None)
        ramp_override = config.get("motor.sangaboard_ramp_time_us", None)
        self._sangaboard_step_override = step_override is not None
        self._sangaboard_ramp_override = ramp_override is not None
        self._sangaboard_step_time_us = self._clamp_sangaboard_step_time(
            step_override if step_override is not None else 1000
        )
        self._sangaboard_ramp_time_us = self._clamp_sangaboard_ramp_time(
            ramp_override if ramp_override is not None else 0
        )
        self._sangaboard_step_override_value = (
            self._sangaboard_step_time_us if self._sangaboard_step_override else None
        )
        self._sangaboard_ramp_override_value = (
            self._sangaboard_ramp_time_us if self._sangaboard_ramp_override else None
        )
        # Autofocus
        self._af_preset      = str(config.get("autofocus.speed_preset", "balanced"))
        if self._af_preset not in ("fast", "balanced", "slow", "custom"):
            self._af_preset = "balanced"
        self._af_settle_ms   = max(50,   min(2000, int(config.get("autofocus.settle_ms", 300))))
        self._af_move_start_ms = max(100, min(3000, int(config.get("autofocus.move_start_ms", 800))))
        self._af_coarse_pos  = max(7,   min(41,   int(config.get("autofocus.coarse_positions", 21))))
        if self._af_coarse_pos % 2 == 0:
            self._af_coarse_pos += 1
        self._af_fine_pos    = max(5,   min(41,   int(config.get("autofocus.fine_positions", 21))))
        if self._af_fine_pos % 2 == 0:
            self._af_fine_pos += 1
        self._af_samples     = max(1,   min(5,    int(config.get("autofocus.samples_per_position", 2))))
        self._af_min_conf    = max(0.0, min(5000.0, float(config.get("autofocus.min_confidence", 50.0))))
        # Camera. The "resolution" and "fps" here are the analysis-tap params (for e.g. histogram/focus pipeline)
        self._cam_dev    = str(config.get("camera.device", "/dev/video0"))
        self._cam_res    = self._clamp_analysis_resolution(
            str(config.get("camera.resolution", "640x360"))
        )
        self._cam_fps    = self._clamp_analysis_fps(int(config.get("camera.fps", 8)))
        self._cam_fmt    = str(config.get("camera.image_format", "OME-TIFF"))
        self._cam_name   = str(config.get("camera.naming_pattern", "{date}_{time}_{obj}"))
        self._cam_frame_analysis = bool(config.get("camera.frame_analysis_enabled", True))
        self._cam_live_video = bool(config.get("camera.live_video_enabled", True))
        # System
        self._restart_after_update = bool(config.get("system.restart_after_update", True))
        # Disk stats (refresh via refreshStorage())
        self._disk_used  = 0
        self._disk_total = 1
        self._cap_count  = 0
        self._refresh_storage()

    @Slot()
    def resetToDefaults(self) -> None:
        if hasattr(self._config, "reset_to_defaults"):
            self._config.reset_to_defaults()

    def _on_config_changed(self, key: str) -> None:
        if key != CONFIG_RESET_KEY:
            return
        self._load_from_config()
        self._emit_all_settings_changed()
        self.applySangaboardTimingOverrides()

    def _emit_all_settings_changed(self) -> None:
        self.joystick_deadzone_changed.emit(self._deadzone)
        self.joystick_curve_changed.emit(self._curve)
        self.joystick_expo_changed.emit(self._expo)
        self.joystick_sensitivity_changed.emit(self._sensitivity)
        self.joystick_swap_xy_changed.emit(self._swap_xy)
        self.joystick_invert_x_changed.emit(self._invert_x)
        self.joystick_invert_y_changed.emit(self._invert_y)
        self.z_encoder_sensitivity_changed.emit(self._z_encoder_sensitivity)
        self.max_pan_speed_changed.emit(self._max_pan_speed)
        self.z_encoder_step_multiplier_changed.emit(self._z_enc_mult)
        self.sangaboard_step_time_changed.emit(self._sangaboard_step_time_us)
        self.sangaboard_ramp_time_changed.emit(self._sangaboard_ramp_time_us)
        self.autofocus_speed_preset_changed.emit(self._af_preset)
        self.autofocus_settle_ms_changed.emit(self._af_settle_ms)
        self.autofocus_move_start_ms_changed.emit(self._af_move_start_ms)
        self.autofocus_coarse_positions_changed.emit(self._af_coarse_pos)
        self.autofocus_fine_positions_changed.emit(self._af_fine_pos)
        self.autofocus_samples_per_position_changed.emit(self._af_samples)
        self.autofocus_min_confidence_changed.emit(self._af_min_conf)
        self.camera_device_changed.emit(self._cam_dev)
        self.camera_resolution_changed.emit(self._cam_res)
        self.camera_fps_changed.emit(self._cam_fps)
        self.camera_format_changed.emit(self._cam_fmt)
        self.camera_naming_changed.emit(self._cam_name)
        self.camera_frame_analysis_changed.emit(self._cam_frame_analysis)
        self.camera_live_video_changed.emit(self._cam_live_video)
        self.capture_root_changed.emit(self.captureRoot)
        self.storage_changed.emit()
        self.restart_after_update_changed.emit(self._restart_after_update)

    # Joystick properties
    @Property(int, notify=joystick_deadzone_changed)
    def joystickDeadzonePct(self) -> int:
        return self._deadzone

    @Slot(int)
    def setJoystickDeadzonePct(self, v: int) -> None:
        v = max(0, min(50, v))
        if v == self._deadzone:
            return
        self._deadzone = v
        self._config.set("input.deadzone_pct", v)
        self.joystick_deadzone_changed.emit(v)

    @Property(str, notify=joystick_curve_changed)
    def joystickCurve(self) -> str:
        return self._curve

    @Slot(str)
    def setJoystickCurve(self, v: str) -> None:
        if v not in ("linear", "exponential", "scurve"):
            return
        if v == self._curve:
            return
        self._curve = v
        self._config.set("input.curve", v)
        self.joystick_curve_changed.emit(v)

    @Property(int, notify=joystick_expo_changed)
    def joystickExpoStrength(self) -> int:
        return self._expo

    @Slot(int)
    def setJoystickExpoStrength(self, v: int) -> None:
        v = max(0, min(100, v))
        if v == self._expo:
            return
        self._expo = v
        self._config.set("input.expo_strength", v)
        self.joystick_expo_changed.emit(v)

    @Property(int, notify=joystick_sensitivity_changed)
    def joystickSensitivityPct(self) -> int:
        return self._sensitivity

    @Slot(int)
    def setJoystickSensitivityPct(self, v: int) -> None:
        v = max(10, min(300, int(v)))
        if v == self._sensitivity:
            return
        self._sensitivity = v
        self._config.set("input.sensitivity_pct", v)
        self.joystick_sensitivity_changed.emit(v)

    @Property(bool, notify=joystick_swap_xy_changed)
    def joystickSwapXY(self) -> bool:
        return self._swap_xy

    @Slot(bool)
    def setJoystickSwapXY(self, v: bool) -> None:
        if v == self._swap_xy:
            return
        self._swap_xy = v
        self._config.set("input.swap_xy", v)
        self.joystick_swap_xy_changed.emit(v)

    @Property(bool, notify=joystick_invert_x_changed)
    def joystickInvertX(self) -> bool:
        return self._invert_x

    @Slot(bool)
    def setJoystickInvertX(self, v: bool) -> None:
        if v == self._invert_x:
            return
        self._invert_x = v
        self._config.set("input.invert_x", v)
        self.joystick_invert_x_changed.emit(v)

    @Property(bool, notify=joystick_invert_y_changed)
    def joystickInvertY(self) -> bool:
        return self._invert_y

    @Slot(bool)
    def setJoystickInvertY(self, v: bool) -> None:
        if v == self._invert_y:
            return
        self._invert_y = v
        self._config.set("input.invert_y", v)
        self.joystick_invert_y_changed.emit(v)

    @Property(int, notify=z_encoder_sensitivity_changed)
    def zEncoderSensitivityPct(self) -> int:
        return self._z_encoder_sensitivity

    @Slot(int)
    def setZEncoderSensitivityPct(self, v: int) -> None:
        v = max(25, min(400, int(v)))
        if v == self._z_encoder_sensitivity:
            return
        self._z_encoder_sensitivity = v
        self._config.set("input.z_encoder_sensitivity_pct", v)
        self.z_encoder_sensitivity_changed.emit(v)


    # Calibration-derived motion globals
    @Property(int, notify=max_pan_speed_changed)
    def maxPanSpeedPxPerSec(self) -> int:
        return self._max_pan_speed

    @Slot(int)
    def setMaxPanSpeedPxPerSec(self, v: int) -> None:
        v = max(10, min(4000, int(v)))
        if v == self._max_pan_speed:
            return
        self._max_pan_speed = v
        self._config.set("input.max_pan_speed_px_per_sec", v)
        self.max_pan_speed_changed.emit(v)

    @Property(float, notify=z_encoder_step_multiplier_changed)
    def zEncoderStepMultiplier(self) -> float:
        return self._z_enc_mult

    @Slot(float)
    def setZEncoderStepMultiplier(self, v: float) -> None:
        v = round(max(0.25, min(4.0, float(v))), 2)
        if v == self._z_enc_mult:
            return
        self._z_enc_mult = v
        self._config.set("input.z_encoder_step_multiplier", v)
        self.z_encoder_step_multiplier_changed.emit(v)

    # Sangaboard
    @Property(int, notify=sangaboard_step_time_changed)
    def sangaboardStepTimeUs(self) -> int:
        return self._sangaboard_step_time_us

    @Slot(int)
    def setSangaboardStepTimeUs(self, v: int) -> None:
        v = self._snap_sangaboard_step_time(v)
        changed = v != self._sangaboard_step_time_us
        self._sangaboard_step_time_us = v
        self._sangaboard_step_override = True
        self._sangaboard_step_override_value = v
        self._config.set("motor.sangaboard_step_time_us", v)
        if changed:
            self.sangaboard_step_time_changed.emit(v)
        self.sangaboard_step_time_set_requested.emit(v)

    @Property(int, notify=sangaboard_ramp_time_changed)
    def sangaboardRampTimeUs(self) -> int:
        return self._sangaboard_ramp_time_us

    @Slot(int)
    def setSangaboardRampTimeUs(self, v: int) -> None:
        v = self._snap_sangaboard_ramp_time(v)
        changed = v != self._sangaboard_ramp_time_us
        self._sangaboard_ramp_time_us = v
        self._sangaboard_ramp_override = True
        self._sangaboard_ramp_override_value = v
        self._config.set("motor.sangaboard_ramp_time_us", v)
        if changed:
            self.sangaboard_ramp_time_changed.emit(v)
        self.sangaboard_ramp_time_set_requested.emit(v)

    @Slot(int, int)
    def onSangaboardTimingUpdated(self, step_time_us: int, ramp_time_us: int) -> None:
        step = self._clamp_sangaboard_step_time(step_time_us)
        ramp = self._clamp_sangaboard_ramp_time(ramp_time_us)
        if step != self._sangaboard_step_time_us:
            self._sangaboard_step_time_us = step
            self.sangaboard_step_time_changed.emit(step)
        if ramp != self._sangaboard_ramp_time_us:
            self._sangaboard_ramp_time_us = ramp
            self.sangaboard_ramp_time_changed.emit(ramp)

    @Slot()
    def applySangaboardTimingOverrides(self) -> None:
        if self._sangaboard_step_override and self._sangaboard_step_override_value is not None:
            self.sangaboard_step_time_set_requested.emit(self._sangaboard_step_override_value)
        if self._sangaboard_ramp_override and self._sangaboard_ramp_override_value is not None:
            self.sangaboard_ramp_time_set_requested.emit(self._sangaboard_ramp_override_value)


    # Autofocus properties

    # Selecting one of the named presets pushes all four matched values, "custom" leaves them alone so they can be tweaked individually.
    _AUTOFOCUS_PRESETS: dict[str, dict[str, int]] = {
        "fast":     {"settle_ms": 150, "move_start_ms": 400,  "coarse": 11, "fine": 13, "samples": 1},
        "balanced": {"settle_ms": 300, "move_start_ms": 800,  "coarse": 21, "fine": 21, "samples": 2},
        "slow":     {"settle_ms": 600, "move_start_ms": 1500, "coarse": 31, "fine": 31, "samples": 3},
    }

    @Property(str, notify=autofocus_speed_preset_changed)
    def autofocusSpeedPreset(self) -> str:
        return self._af_preset

    @Slot(str)
    def setAutofocusSpeedPreset(self, v: str) -> None:
        v = str(v).strip().lower()
        if v not in ("fast", "balanced", "slow", "custom"):
            return
        if v != self._af_preset:
            self._af_preset = v
            self._config.set("autofocus.speed_preset", v)
            self.autofocus_speed_preset_changed.emit(v)
        if v in self._AUTOFOCUS_PRESETS:
            preset = self._AUTOFOCUS_PRESETS[v]
            self.setAutofocusSettleMs(preset["settle_ms"])
            self.setAutofocusMoveStartMs(preset["move_start_ms"])
            self.setAutofocusCoarsePositions(preset["coarse"])
            self.setAutofocusFinePositions(preset["fine"])
            self.setAutofocusSamplesPerPosition(preset["samples"])

    @Property(int, notify=autofocus_settle_ms_changed)
    def autofocusSettleMs(self) -> int:
        return self._af_settle_ms

    @Slot(int)
    def setAutofocusSettleMs(self, v: int) -> None:
        v = max(1000, min(3000, int(v)))
        if v == self._af_settle_ms:
            return
        self._af_settle_ms = v
        self._config.set("autofocus.settle_ms", v)
        self.autofocus_settle_ms_changed.emit(v)

    @Property(int, notify=autofocus_move_start_ms_changed)
    def autofocusMoveStartMs(self) -> int:
        return self._af_move_start_ms

    @Slot(int)
    def setAutofocusMoveStartMs(self, v: int) -> None:
        v = max(100, min(3000, int(v)))
        if v == self._af_move_start_ms:
            return
        self._af_move_start_ms = v
        self._config.set("autofocus.move_start_ms", v)
        self.autofocus_move_start_ms_changed.emit(v)

    @Property(int, notify=autofocus_coarse_positions_changed)
    def autofocusCoarsePositions(self) -> int:
        return self._af_coarse_pos

    @Slot(int)
    def setAutofocusCoarsePositions(self, v: int) -> None:
        v = max(7, min(41, int(v)))
        if v % 2 == 0:
            v += 1   # keep it odd for symmetric centre-out sweep
        if v == self._af_coarse_pos:
            return
        self._af_coarse_pos = v
        self._config.set("autofocus.coarse_positions", v)
        self.autofocus_coarse_positions_changed.emit(v)

    @Property(int, notify=autofocus_fine_positions_changed)
    def autofocusFinePositions(self) -> int:
        return self._af_fine_pos

    @Slot(int)
    def setAutofocusFinePositions(self, v: int) -> None:
        v = max(5, min(41, int(v)))
        if v % 2 == 0:
            v += 1
        if v == self._af_fine_pos:
            return
        self._af_fine_pos = v
        self._config.set("autofocus.fine_positions", v)
        self.autofocus_fine_positions_changed.emit(v)

    @Property(int, notify=autofocus_samples_per_position_changed)
    def autofocusSamplesPerPosition(self) -> int:
        return self._af_samples

    @Slot(int)
    def setAutofocusSamplesPerPosition(self, v: int) -> None:
        v = max(1, min(5, int(v)))
        if v == self._af_samples:
            return
        self._af_samples = v
        self._config.set("autofocus.samples_per_position", v)
        self.autofocus_samples_per_position_changed.emit(v)

    @Property(float, notify=autofocus_min_confidence_changed)
    def autofocusMinConfidence(self) -> float:
        return self._af_min_conf

    @Slot(float)
    def setAutofocusMinConfidence(self, v: float) -> None:
        v = round(max(0.0, min(5000.0, float(v))), 1)
        if v == self._af_min_conf:
            return
        self._af_min_conf = v
        self._config.set("autofocus.min_confidence", v)
        self.autofocus_min_confidence_changed.emit(v)


    # Camera properties
    @Property(str, notify=camera_device_changed)
    def cameraDevice(self) -> str:
        return self._cam_dev

    @Slot(str)
    def setCameraDevice(self, v: str) -> None:
        if v == self._cam_dev:
            return
        self._cam_dev = v
        self._config.set("camera.device", v)
        self.camera_device_changed.emit(v)

    @Property(str, notify=camera_resolution_changed)
    def cameraResolution(self) -> str:
        return self._cam_res

    @Slot(str)
    def setCameraResolution(self, v: str) -> None:
        v = self._clamp_analysis_resolution(v)
        if v == self._cam_res:
            return
        self._cam_res = v
        self._config.set("camera.resolution", v)
        self.camera_resolution_changed.emit(v)

    @Property(int, notify=camera_fps_changed)
    def cameraFps(self) -> int:
        return self._cam_fps

    @Slot(int)
    def setCameraFps(self, v: int) -> None:
        v = self._clamp_analysis_fps(v)
        if v == self._cam_fps:
            return
        self._cam_fps = v
        self._config.set("camera.fps", v)
        self.camera_fps_changed.emit(v)

    @Property(bool, notify=camera_frame_analysis_changed)
    def cameraFrameAnalysisEnabled(self) -> bool:
        return self._cam_frame_analysis

    @Slot(bool)
    def setCameraFrameAnalysisEnabled(self, v: bool) -> None:
        enabled = bool(v)
        if enabled == self._cam_frame_analysis:
            return
        self._cam_frame_analysis = enabled
        self._config.set("camera.frame_analysis_enabled", enabled)
        self.camera_frame_analysis_changed.emit(enabled)

    @Property(bool, notify=camera_live_video_changed)
    def cameraLiveVideoEnabled(self) -> bool:
        return self._cam_live_video

    @Slot(bool)
    def setCameraLiveVideoEnabled(self, v: bool) -> None:
        enabled = bool(v)
        if enabled == self._cam_live_video:
            return
        self._cam_live_video = enabled
        self._config.set("camera.live_video_enabled", enabled)
        self.camera_live_video_changed.emit(enabled)

    @staticmethod
    def _clamp_analysis_resolution(v: str) -> str:
        # Anything wider than 1280 makes the per-frame analysis path too expensive and lags the live view.
        text = str(v).replace("×", "x")
        try:
            w_str, _h_str = text.split("x", 1)
            if int(w_str) > 1280:
                return "1280x720"
        except (ValueError, AttributeError):
            return "640x360"
        return text

    @staticmethod
    def _clamp_analysis_fps(v: int) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return 8
        return max(1, min(10, v))

    @Property(str, notify=camera_format_changed)
    def cameraImageFormat(self) -> str:
        return self._cam_fmt

    @Slot(str)
    def setCameraImageFormat(self, v: str) -> None:
        if v != "OME-TIFF":
            return
        if v == self._cam_fmt:
            return
        self._cam_fmt = v
        self._config.set("camera.image_format", v)
        self.camera_format_changed.emit(v)

    @Property(str, notify=camera_naming_changed)
    def cameraNamingPattern(self) -> str:
        return self._cam_name

    @Slot(str)
    def setCameraNamingPattern(self, v: str) -> None:
        if v == self._cam_name:
            return
        self._cam_name = v
        self._config.set("camera.naming_pattern", v)
        self.camera_naming_changed.emit(v)

    # Storage (read-only, refreshed on demand)
    @Property(str, notify=capture_root_changed)
    def captureRoot(self) -> str:
        return str(self._store.capture_root())

    @Slot(str)
    def setCaptureRoot(self, v: str) -> None:
        clean = str(v).strip()
        if clean == "":
            return
        expanded = str(Path(clean).expanduser())
        if expanded == str(self._store.capture_root()):
            return
        self._config.set("captures.root", expanded)
        self._config.save()
        self._store.ensure_directories()
        self.capture_root_changed.emit(expanded)
        self.refreshStorage()

    @Property(float, notify=storage_changed)
    def diskUsedGb(self) -> float:
        return self._disk_used / 1_073_741_824.0

    @Property(float, notify=storage_changed)
    def diskTotalGb(self) -> float:
        return max(0.001, self._disk_total / 1_073_741_824.0)

    @Property(float, notify=storage_changed)
    def diskUsedFraction(self) -> float:
        return min(1.0, self._disk_used / max(1, self._disk_total))

    @Property(int, notify=storage_changed)
    def captureCount(self) -> int:
        return self._cap_count

    @Slot()
    def refreshStorage(self) -> None:
        self._refresh_storage()
        self.storage_changed.emit()

    @Slot()
    def clearAllCaptures(self) -> None:
        self._store.clear_all()
        self._refresh_storage()
        self.storage_changed.emit()


    # System properties
    @Property(bool, notify=restart_after_update_changed)
    def restartAfterUpdate(self) -> bool:
        return self._restart_after_update

    @Slot(bool)
    def setRestartAfterUpdate(self, v: bool) -> None:
        if v == self._restart_after_update:
            return
        self._restart_after_update = v
        self._config.set("system.restart_after_update", v)
        self.restart_after_update_changed.emit(v)


    # Internal
    @staticmethod
    def _clamp_sangaboard_step_time(v: int) -> int:
        return max(50, min(10000, int(v)))

    @staticmethod
    def _clamp_sangaboard_ramp_time(v: int) -> int:
        return max(0, min(500000, int(v)))

    @classmethod
    def _snap_sangaboard_step_time(cls, v: int) -> int:
        v = int(round(float(v) / 50.0) * 50)
        return cls._clamp_sangaboard_step_time(v)

    @classmethod
    def _snap_sangaboard_ramp_time(cls, v: int) -> int:
        v = int(round(float(v) / 5000.0) * 5000)
        return cls._clamp_sangaboard_ramp_time(v)

    def _refresh_storage(self) -> None:
        try:
            usage = shutil.disk_usage(self._store.capture_root())
            self._disk_used  = usage.used
            self._disk_total = max(1, usage.total)
        except Exception:
            self._disk_used  = 0
            self._disk_total = 1
        try:
            self._cap_count = self._store.total_count()
        except Exception:
            self._cap_count = 0
