"""Bridge and QML image-provider construction."""

from __future__ import annotations

from retroscope.app.containers import Bridges, ImageProviders, Services
from retroscope.app.services import create_automation_services


def create_bridges(services: Services) -> tuple[Bridges, ImageProviders]:
    """Create QML bridges and image providers."""
    from retroscope.bridge.autofocus_bridge import AutofocusBridge
    from retroscope.bridge.automation_bridge import AutomationBridge
    from retroscope.bridge.button_bridge import ButtonBridge
    from retroscope.bridge.calibration_bridge import CalibrationBridge
    from retroscope.bridge.camera_provider import (
        CameraImageProvider,
        OmeTiffImageProvider,
    )
    from retroscope.bridge.gallery_bridge import GalleryBridge
    from retroscope.bridge.measurement_bridge import MeasurementBridge
    from retroscope.bridge.motion_bridge import MotionBridge
    from retroscope.bridge.objective_bridge import ObjectiveBridge
    from retroscope.bridge.objective_detector_bridge import ObjectiveDetectorBridge
    from retroscope.bridge.overlay_bridge import OverlayBridge
    from retroscope.bridge.settings_bridge import SettingsBridge
    from retroscope.bridge.status_bridge import StatusBridge
    from retroscope.bridge.system_bridge import SystemBridge
    from retroscope.bridge.update_bridge import UpdateBridge

    motion_bridge = MotionBridge(services.motion_ctrl)
    objective_bridge = ObjectiveBridge(services.objective_mgr)
    overlay_bridge = OverlayBridge(services.config)
    get_position = lambda: (motion_bridge.posX, motion_bridge.posY, motion_bridge.posZ)

    gallery_bridge = GalleryBridge(
        services.image_store,
        services.motion_ctrl,
        services.objective_mgr,
        get_position=get_position,
    )
    status_bridge = StatusBridge()
    update_bridge = UpdateBridge(services.update_svc)
    system_bridge = SystemBridge(services.system_svc)
    button_bridge = ButtonBridge(services.button_mgr)
    autofocus_bridge = AutofocusBridge(services.autofocus_svc)
    measurement_bridge = MeasurementBridge()
    calibration_bridge = CalibrationBridge(
        services.camera_svc,
        services.motion_ctrl,
        services.objective_mgr,
        services.config,
    )
    objective_detector_bridge = ObjectiveDetectorBridge(
        services.objective_detector,
        services.config,
    )
    settings_bridge = SettingsBridge(services.config, services.storage_svc)

    create_automation_services(services, get_position)
    automation_bridge = AutomationBridge(
        services.focus_stacker_svc,
        services.tile_scanner_svc,
    )

    services.camera_svc.set_metadata_provider(
        get_position=get_position,
        get_objective=lambda: objective_bridge.activeObjective,
    )

    bridges = Bridges(
        motion=motion_bridge,
        objective=objective_bridge,
        overlay=overlay_bridge,
        gallery=gallery_bridge,
        status=status_bridge,
        update=update_bridge,
        system=system_bridge,
        buttons=button_bridge,
        autofocus=autofocus_bridge,
        measurement=measurement_bridge,
        automation=automation_bridge,
        calibration=calibration_bridge,
        settings=settings_bridge,
        obj_detector=objective_detector_bridge,
    )
    providers = ImageProviders(
        camera=CameraImageProvider(services.camera_svc),
        ome=OmeTiffImageProvider(),
    )
    return bridges, providers


def create_app_controller(app, services: Services, bridges: Bridges):
    """Create the root QObject exposed to QML as App."""
    from retroscope.bridge.app_controller import AppController

    return AppController(
        motion=bridges.motion,
        objective=bridges.objective,
        overlay=bridges.overlay,
        gallery=bridges.gallery,
        status=bridges.status,
        update=bridges.update,
        system=bridges.system,
        buttons=bridges.buttons,
        autofocus=bridges.autofocus,
        measurement=bridges.measurement,
        automation=bridges.automation,
        calibration=bridges.calibration,
        settings=bridges.settings,
        obj_detector=bridges.obj_detector,
        camera_svc=services.camera_svc,
        measurement_capture_svc=services.measurement_capture_svc,
        parent=app,
    )
