"""Application runner that coordinates bootstrap, QML, shutdown..."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from retroscope.app.bridges import create_app_controller, create_bridges
from retroscope.app.drivers import create_drivers, start_drivers
from retroscope.app.lifecycle import (
    install_keyboard_shortcuts,
    shutdown_and_exit,
)
from retroscope.app.qml_engine import create_qml_engine, load_main_qml
from retroscope.app.qt_setup import create_application, force_mock_platform
from retroscope.app.services import create_services, load_config
from retroscope.app.wiring import (
    register_button_actions,
    wire_app_controller_signals,
    wire_signals,
)

QML_PATH = Path(__file__).resolve().parents[1] / "qml"


def run_application(args) -> None:
    """Run the Qt application."""

    if args.mock:
        force_mock_platform()

    app = create_application(scale=args.scale)
    config = load_config()
    drivers = create_drivers()
    services = create_services(config, drivers)
    api_service = services.rest_api_svc
    bridges, providers = create_bridges(services)
    register_button_actions(services)
    wire_signals(drivers, services, bridges)

    start_drivers(drivers)

    app_controller = create_app_controller(app, services, bridges)
    wire_app_controller_signals(drivers, app_controller)

    engine = create_qml_engine(app_controller, providers)
    app.aboutToQuit.connect(app_controller.shutdown)

    if args.dev or os.environ.get("HOT_RELOAD") == "1":
        from retroscope.hot_reload import HotReloader

        reloader = HotReloader(engine, QML_PATH)
        reloader.start()

    load_main_qml(engine, QML_PATH)

    if not engine.rootObjects():
        print("ERROR: Failed to load QML root", file=sys.stderr)
        app_controller.shutdown()
        if api_service is not None:
            api_service.stop()
        shutdown_and_exit(drivers, config, 1)

    install_keyboard_shortcuts(app, services, drivers)

    if api_service is not None:
        api_service.start()
        app.aboutToQuit.connect(api_service.stop)

    exit_code = app.exec()
    app_controller.shutdown()
    if api_service is not None:
        api_service.stop()
    shutdown_and_exit(drivers, config, exit_code)
