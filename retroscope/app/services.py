"""Service construction for the application."""

from __future__ import annotations

from retroscope.app.containers import Drivers, Services


def load_config():
    """Load the persistent application configuration."""
    from retroscope.services.config_store import ConfigStore

    config = ConfigStore()
    config.load()
    return config

def create_services(config, drivers: Drivers) -> Services:
    """Create services that do not depend on QML bridge state."""
    from retroscope.services.autofocus import AutofocusService
    from retroscope.services.button_manager import ButtonManager
    from retroscope.services.camera_service import CameraService
    from retroscope.services.image_store import ImageStore
    from retroscope.services.input_manager import InputManager
    from retroscope.services.measurement_capture import MeasurementCaptureService
    from retroscope.services.motion_controller import MotionController
    from retroscope.services.objective_detector import ObjectiveDetector
    from retroscope.services.objective_manager import ObjectiveManager
    from retroscope.services.storage_service import StorageService
    from retroscope.services.system_service import SystemService
    from retroscope.services.update_service import UpdateService
    from retroscope.api.dispatcher import QtCommandDispatcher
    from retroscope.api.service import RestApiService

    objective_mgr = ObjectiveManager(config)
    motion_ctrl = MotionController(drivers.sangaboard, objective_mgr, config)
    image_store = ImageStore(config)
    image_store.ensure_directories()
    camera_svc = CameraService(config, image_store=image_store)
    input_mgr = InputManager(drivers.ads, drivers.encoder, motion_ctrl)
    button_mgr = ButtonManager(drivers.buttons, config)
    update_svc = UpdateService(config)
    system_svc = SystemService(config)
    autofocus_svc = AutofocusService(camera_svc, motion_ctrl, objective_mgr, config)
    objective_detector = ObjectiveDetector(config)
    measurement_capture_svc = MeasurementCaptureService()
    storage_svc = StorageService(config, image_store)
    api_dispatcher = QtCommandDispatcher()
    rest_api_svc = RestApiService(
        config,
        image_store=image_store,
        autofocus_svc=autofocus_svc,
        dispatcher=api_dispatcher,
    )

    return Services(
        config=config,
        objective_mgr=objective_mgr,
        motion_ctrl=motion_ctrl,
        image_store=image_store,
        camera_svc=camera_svc,
        input_mgr=input_mgr,
        button_mgr=button_mgr,
        update_svc=update_svc,
        system_svc=system_svc,
        autofocus_svc=autofocus_svc,
        objective_detector=objective_detector,
        measurement_capture_svc=measurement_capture_svc,
        storage_svc=storage_svc,
        rest_api_svc=rest_api_svc,
    )

def create_automation_services(services: Services, get_position) -> None:
    """Attach automation services after the motion bridge exists."""
    from retroscope.services.focus_stacker import FocusStackerService
    from retroscope.services.tile_scanner import TileScannerService

    services.focus_stacker_svc = FocusStackerService(
        services.camera_svc,
        services.motion_ctrl,
        services.image_store,
        services.objective_mgr,
        get_position=get_position,
    )
    services.tile_scanner_svc = TileScannerService(
        services.camera_svc,
        services.motion_ctrl,
        services.autofocus_svc,
        services.image_store,
        services.objective_mgr,
        get_position=get_position,
    )
