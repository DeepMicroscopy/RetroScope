"""System bridge: App restart and Pi shutdown for QML SettingsView."""

import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from retroscope.platform import is_pi
from retroscope.services.config_store import _CONFIG_FILE
from retroscope.services.system_service import SystemService


def _opencv_version() -> str:
    try:
        import cv2
        return cv2.__version__
    except Exception:
        return "n/a"


def _pyside6_version() -> str:
    try:
        import PySide6
        return PySide6.__version__
    except Exception:
        return "n/a"


class SystemBridge(QObject):
    shutdown_initiated = Signal()

    def __init__(self, service: SystemService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._svc = service
        service.shutdown_initiated.connect(self.shutdown_initiated)
        self._python_ver  = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self._pyside6_ver = _pyside6_version()
        self._opencv_ver  = _opencv_version()

    @Property(bool, constant=True)
    def isPi(self) -> bool:
        return is_pi()

    @Property(str, constant=True)
    def pythonVersion(self) -> str:
        return self._python_ver

    @Property(str, constant=True)
    def pyside6Version(self) -> str:
        return self._pyside6_ver

    @Property(str, constant=True)
    def opencvVersion(self) -> str:
        return self._opencv_ver

    @Property(str, constant=True)
    def configPath(self) -> str:
        return str(_CONFIG_FILE)

    @Slot()
    def restartApp(self) -> None:
        self._svc.restart_app()

    @Slot()
    def shutdownPi(self) -> None:
        self._svc.shutdown_pi()

    @Slot()
    def quitApp(self) -> None:
        self._svc.quit_app()

    @Slot()
    def showInputPanel(self) -> None:
        QGuiApplication.inputMethod().show()
