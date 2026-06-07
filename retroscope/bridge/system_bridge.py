"""System bridge: App restart and Pi shutdown for QML SettingsView."""

import socket
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


def _current_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            host = sock.getsockname()[0]
            if host:
                return str(host)
    except Exception:
        pass
    try:
        host = socket.gethostbyname(socket.gethostname())
        if host:
            return str(host)
    except Exception:
        pass
    return "127.0.0.1"


def _host_for_url(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


class SystemBridge(QObject):
    shutdown_initiated = Signal()
    network_info_changed = Signal()

    def __init__(self, service: SystemService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._svc = service
        self._config = getattr(service, "_config", None)
        service.shutdown_initiated.connect(self.shutdown_initiated)
        self._python_ver  = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        self._pyside6_ver = _pyside6_version()
        self._opencv_ver  = _opencv_version()
        self._current_ip = _current_ip_address()

    def _config_get(self, key: str, default):
        if self._config is None or not hasattr(self._config, "get"):
            return default
        return self._config.get(key, default)

    def _api_enabled(self) -> bool:
        return bool(self._config_get("api.enabled", True))

    def _api_host(self) -> str:
        configured = str(self._config_get("api.host", "0.0.0.0") or "0.0.0.0").strip()
        if configured in ("", "0.0.0.0", "::"):
            return self._current_ip
        return configured

    def _api_port(self) -> int:
        try:
            return int(self._config_get("api.port", 8765))
        except (TypeError, ValueError):
            return 8765

    def _api_url(self, path: str = "") -> str:
        if not self._api_enabled():
            return "Disabled"
        return f"http://{_host_for_url(self._api_host())}:{self._api_port()}{path}"

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

    @Property(str, notify=network_info_changed)
    def currentIpAddress(self) -> str:
        return self._current_ip

    @Property(str, notify=network_info_changed)
    def apiBaseUrl(self) -> str:
        return self._api_url()

    @Property(str, notify=network_info_changed)
    def apiDocsUrl(self) -> str:
        if not bool(self._config_get("api.docs_enabled", True)) or not self._api_enabled():
            return "Disabled"
        return self._api_url("/docs")

    @Slot()
    def refreshNetworkInfo(self) -> None:
        self._current_ip = _current_ip_address()
        self.network_info_changed.emit()

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
