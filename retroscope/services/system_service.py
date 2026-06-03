"""System control: App restart and Raspberry Pi shutdown.

Restart: exits with code 42, start.sh relaunches the app.
Shutdown: runs 'sudo shutdown -h now' (Pi only).
"""

import subprocess

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from retroscope.platform import is_pi
from retroscope.services.config_store import ConfigStore


class SystemService(QObject):
    """Provides app restart and Pi shutdown actions."""

    shutdown_initiated = Signal()   # emitted just before shutdown

    def __init__(self, config: ConfigStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config

    @Slot()
    def restart_app(self) -> None:
        """Save config and restart the app (exit code 42)."""
        self._config.save()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.exit(42)

    @Slot()
    def shutdown_pi(self) -> None:
        """Shut down the Raspberry Pi. No function on macOS."""
        if not is_pi():
            return
        self._config.save()
        self.shutdown_initiated.emit()
        # Delay slightly so Qt can process the signals before the OS shuts down
        QTimer.singleShot(2000, self._do_shutdown)

    @Slot()
    def quit_app(self) -> None:
        """Exit the application cleanly (exit code 0, start.sh will NOT restart)."""
        self._config.save()
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.exit(0)

    def _do_shutdown(self) -> None:
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
        except Exception:
            pass
