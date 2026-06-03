"""QML engine setup."""

from __future__ import annotations

from pathlib import Path

from retroscope.app.containers import ImageProviders


def create_qml_engine(app_controller, providers: ImageProviders):
    """Create the QML engine and expose root objects/providers."""
    from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
    from PySide6.QtQuickControls2 import QQuickStyle

    QQuickStyle.setStyle("Basic")
    qmlRegisterSingletonInstance(
        type(app_controller),
        "RetroScope",
        1,
        0,
        "App",
        app_controller,
    )

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("App", app_controller)
    engine.addImageProvider("camera", providers.camera)
    engine.addImageProvider("ome", providers.ome)
    return engine


def load_main_qml(engine, qml_path: Path) -> None:
    """Load the root QML file."""
    from PySide6.QtCore import QUrl

    engine.load(QUrl.fromLocalFile(str(qml_path / "main.qml")))
