"""Signal and action wiring."""

from __future__ import annotations

from retroscope.app.containers import Bridges, Drivers, Services

def register_button_actions(services: Services) -> None:
    """Register user-configurable physical button actions."""
    services.button_mgr.register_action(
        "snapshot",
        "Capture",
        lambda: services.camera_svc.capture_snapshot(),
    )
    services.button_mgr.register_action(
        "toggle_recording",
        "Start/Stop Recording",
        lambda: (
            services.camera_svc.stop_recording()
            if services.camera_svc.is_recording()
            else services.camera_svc.start_recording()
        ),
    )
    services.button_mgr.register_action(
        "autofocus",
        "Autofocus",
        lambda: services.autofocus_svc.toggle(),
    )
    services.button_mgr.register_action(
        "emergency_stop",
        "Emergency Stop",
        lambda: services.motion_ctrl.emergency_stop(),
    )

def wire_signals(
    drivers: Drivers,
    services: Services,
    bridges: Bridges,
) -> None:
    """Connect drivers, services and bridge signals."""
    drivers.sangaboard.position_updated.connect(services.motion_ctrl.on_position_updated)
    drivers.sangaboard.position_updated.connect(bridges.motion.on_position_updated)
    drivers.sangaboard.motion_timing_updated.connect(bridges.settings.onSangaboardTimingUpdated)
    services.motion_ctrl.position_reset.connect(bridges.motion.on_position_updated)
    drivers.sangaboard.connected_changed.connect(bridges.status.on_connection_changed)
    # On Sangaboard (re)connect: Invalidate the backlash slack-band state.
    # Beause the stage may have been moved while disconnected.
    drivers.sangaboard.connected_changed.connect(
        lambda connected: services.motion_ctrl.invalidate_backlash_history() if connected else None
    )
    drivers.sangaboard.connected_changed.connect(
        lambda connected: drivers.sangaboard.request_motion_timing() if connected else None
    )
    drivers.sangaboard.connected_changed.connect(
        lambda connected: bridges.settings.applySangaboardTimingOverrides() if connected else None
    )

    drivers.endstop.triggered.connect(services.motion_ctrl.on_endstop_triggered)
    drivers.endstop.triggered.connect(bridges.status.on_endstop_changed)

    services.motion_ctrl.motion_blocked.connect(bridges.motion.motion_blocked)
    bridges.motion.z_move_requested.connect(services.motion_ctrl.move_z)
    bridges.motion.xy_move_requested.connect(services.motion_ctrl.move_rel_xy)
    bridges.motion.motors_deenergize_requested.connect(services.motion_ctrl.deenergize_motors)
    bridges.motion.joystick_cal_requested.connect(services.motion_ctrl.startJoystickCal)
    services.motion_ctrl.joystick_cal_done.connect(bridges.motion.joystickCalDone)
    services.motion_ctrl.joystick_center_changed.connect(
        lambda: bridges.motion.on_joystick_center_updated(
            services.motion_ctrl.joystickCenterX,
            services.motion_ctrl.joystickCenterY,
        )
    )
    bridges.motion.deadzone_set_requested.connect(services.motion_ctrl.setDeadzone)

    bridges.settings.joystick_deadzone_changed.connect(
        lambda pct: services.motion_ctrl.setDeadzone(pct / 100.0)
    )
    bridges.settings.joystick_deadzone_changed.connect(
        lambda pct: bridges.motion.on_deadzone_updated(pct / 100.0)
    )
    initial_deadzone_pct = services.config.get("input.deadzone_pct", 8)
    services.motion_ctrl.setDeadzone(initial_deadzone_pct / 100.0)
    bridges.motion.on_deadzone_updated(initial_deadzone_pct / 100.0)

    bridges.settings.joystick_swap_xy_changed.connect(services.motion_ctrl.setJoystickSwapXY)
    bridges.settings.joystick_swap_xy_changed.connect(bridges.motion.setJoystickSwapXY)
    bridges.settings.joystick_invert_x_changed.connect(services.motion_ctrl.setJoystickInvertX)
    bridges.settings.joystick_invert_x_changed.connect(bridges.motion.setJoystickInvertX)
    bridges.settings.joystick_invert_y_changed.connect(services.motion_ctrl.setJoystickInvertY)
    bridges.settings.joystick_invert_y_changed.connect(bridges.motion.setJoystickInvertY)
    bridges.settings.joystick_curve_changed.connect(services.motion_ctrl.setJoystickCurve)
    bridges.settings.joystick_expo_changed.connect(services.motion_ctrl.setJoystickExpoStrength)
    bridges.settings.joystick_sensitivity_changed.connect(services.motion_ctrl.setJoystickSensitivityPct)
    bridges.settings.joystick_backlash_compensation_changed.connect(
        services.motion_ctrl.setJoystickBacklashCompensationEnabled
    )
    bridges.settings.z_encoder_sensitivity_changed.connect(
        services.motion_ctrl.setZEncoderSensitivityPct
    )
    bridges.settings.max_pan_speed_changed.connect(
        services.motion_ctrl.setMaxPanSpeedPxPerSec
    )
    bridges.settings.z_encoder_step_multiplier_changed.connect(
        services.motion_ctrl.setZEncoderStepMultiplier
    )
    bridges.settings.sangaboard_step_time_set_requested.connect(
        drivers.sangaboard.set_step_time_us
    )
    bridges.settings.sangaboard_ramp_time_set_requested.connect(
        drivers.sangaboard.set_ramp_time_us
    )
    services.motion_ctrl.setJoystickSwapXY(bridges.settings.joystickSwapXY)
    bridges.motion.setJoystickSwapXY(bridges.settings.joystickSwapXY)
    services.motion_ctrl.setJoystickInvertX(bridges.settings.joystickInvertX)
    bridges.motion.setJoystickInvertX(bridges.settings.joystickInvertX)
    services.motion_ctrl.setJoystickInvertY(bridges.settings.joystickInvertY)
    bridges.motion.setJoystickInvertY(bridges.settings.joystickInvertY)
    services.motion_ctrl.setJoystickCurve(bridges.settings.joystickCurve)
    services.motion_ctrl.setJoystickExpoStrength(bridges.settings.joystickExpoStrength)
    services.motion_ctrl.setJoystickSensitivityPct(bridges.settings.joystickSensitivityPct)
    services.motion_ctrl.setJoystickBacklashCompensationEnabled(
        bridges.settings.joystickBacklashCompensationEnabled
    )
    services.motion_ctrl.setZEncoderSensitivityPct(bridges.settings.zEncoderSensitivityPct)
    services.motion_ctrl.setMaxPanSpeedPxPerSec(bridges.settings.maxPanSpeedPxPerSec)
    services.motion_ctrl.setZEncoderStepMultiplier(bridges.settings.zEncoderStepMultiplier)

    drivers.ads.axes_updated.connect(bridges.motion.on_joystick_axes)

    services.camera_svc.snapshot_saved.connect(bridges.gallery.on_capture_saved)
    services.camera_svc.recording_saved.connect(bridges.gallery.on_capture_saved)
    services.focus_stacker_svc.finished.connect(bridges.gallery.on_capture_saved)
    services.tile_scanner_svc.scan_saved.connect(bridges.gallery.on_capture_saved)
    bridges.settings.capture_root_changed.connect(lambda _path: bridges.gallery.refresh())

    from PySide6.QtCore import Qt

    services.camera_svc.brightness_updated.connect(
        services.objective_detector.on_brightness_updated,
        Qt.ConnectionType.DirectConnection,
    )

def wire_app_controller_signals(drivers: Drivers, app_controller) -> None:
    del drivers, app_controller
