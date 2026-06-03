"""QML hot reloader: Watches .qml files and reloads the engine on change.

Activate with: python app.py --dev

Works by debouncing QFileSystemWatcher events then calling
engine.clearComponentCache() + engine.load(). After each reload, all QML
files are re-added to the watcher.

Python state (services, bridges) is untouched across reloads.
QML state (active tab etc.) resets to initial values.

Note: Partially AI-generated
"""

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, QUrl, Signal

class HotReloader(QObject):
    reloaded = Signal(str)  # timestamp string

    def __init__(self, engine, qml_root: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._qml_root = qml_root
        self._root_url = QUrl.fromLocalFile(str(qml_root / "main.qml"))
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._reload)

    def start(self) -> None:
        """Begin watching all .qml files under qml_root."""
        self._add_all_files()

    def _add_all_files(self) -> None:
        paths = [str(p) for p in self._qml_root.rglob("*.qml")]
        if paths:
            self._watcher.addPaths(paths)

    def _on_file_changed(self, _path: str) -> None:
        # Restart debounce timer, fire only after writes settle
        self._debounce.start()

    def _reload(self) -> None:
        from PySide6.QtCore import QDateTime
        ts = QDateTime.currentDateTime().toString("hh:mm:ss")

        # First, destroy existing windows so we don't open duplicate ones on reload
        for r in self._engine.rootObjects():
            r.deleteLater()

        self._engine.clearComponentCache()
        self._engine.load(self._root_url)

        self._add_all_files()

        # Wire reload toast on new root object
        roots = self._engine.rootObjects()
        if roots:
            try:
                roots[0].showReloadToast(ts)
            except Exception:
                pass

        self.reloaded.emit(ts)
