"""Git-based OTA update service.

Checks for updates by comparing local HEAD to remote branch.
Applies updates with git pull --ff-only, then requests app restart (exit 42).
"""

import subprocess

from PySide6.QtCore import QObject, QThread, Signal, Slot

from retroscope.services.config_store import ConfigStore

_GIT_TIMEOUT = 30  # seconds


def _run_git(args: list[str]) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", "git command timed out"
    except FileNotFoundError:
        return 1, "", "git not found"


class _UpdateWorker(QThread):
    """Background worker for blocking git operations."""

    update_found = Signal(bool, str)    # (available, message)
    update_complete = Signal()
    update_failed = Signal(str)
    progress = Signal(str)

    def __init__(self, mode: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mode = mode  # "check" or "apply"

    def run(self) -> None:
        if self._mode == "check":
            self._check()
        elif self._mode == "apply":
            self._apply()

    def _check(self) -> None:
        self.progress.emit("Fetching remote...")
        rc, _, err = _run_git(["fetch", "--quiet"])
        if rc != 0:
            self.update_found.emit(False, f"Fetch failed: {err}")
            return

        self.progress.emit("Comparing versions...")
        rc, local, _ = _run_git(["rev-parse", "HEAD"])
        if rc != 0:
            self.update_found.emit(False, "Cannot read local HEAD")
            return

        rc, remote, _ = _run_git(["rev-parse", "@{u}"])
        if rc != 0:
            self.update_found.emit(False, "No remote tracking branch configured")
            return

        if local == remote:
            self.update_found.emit(False, "Already up to date")
        else:
            rc, log, _ = _run_git(["log", "--oneline", f"HEAD..@{{u}}"])
            count = len(log.splitlines()) if log else 1
            self.update_found.emit(True, f"{count} new commit(s) available")

    def _apply(self) -> None:
        self.progress.emit("Pulling update...")
        rc, out, err = _run_git(["pull", "--ff-only"])
        if rc != 0:
            self.update_failed.emit(err or out or "git pull failed")
        else:
            self.update_complete.emit()


class UpdateService(QObject):
    """Manages OTA update state and spawns workers on demand."""

    update_found = Signal(bool, str)
    update_complete = Signal()
    update_failed = Signal(str)
    progress = Signal(str)

    def __init__(self, config: ConfigStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._worker: _UpdateWorker | None = None
        self._last_restart_requested = False

        # Check if git repo is available
        rc, _, _ = _run_git(["rev-parse", "--git-dir"])
        self._git_available = rc == 0

    @property
    def git_available(self) -> bool:
        return self._git_available

    @property
    def last_restart_requested(self) -> bool:
        return self._last_restart_requested

    def get_version(self) -> str:
        rc, out, _ = _run_git(["describe", "--tags", "--always", "--dirty"])
        return out if rc == 0 and out else "unknown"

    @Slot()
    def check_for_updates(self) -> None:
        if not self._git_available or self._worker_busy():
            return
        self._start_worker("check")

    @Slot()
    def apply_update(self) -> None:
        if not self._git_available or self._worker_busy():
            return
        self._start_worker("apply")

    def _worker_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _start_worker(self, mode: str) -> None:
        self._worker = _UpdateWorker(mode, self)
        self._worker.update_found.connect(self.update_found)
        self._worker.update_complete.connect(self._on_update_complete)
        self._worker.update_failed.connect(self.update_failed)
        self._worker.progress.connect(self.progress)
        self._worker.start()

    @Slot()
    def _on_update_complete(self) -> None:
        self._config.save()
        self._last_restart_requested = bool(self._config.get("system.restart_after_update", True))
        self.update_complete.emit()
        if self._last_restart_requested:
            # Restart app via exit code 42, start.sh will relaunch
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.exit(42)
