"""Bookmark service: Save, list, delete and navigate."""

from PySide6.QtCore import QObject, Signal, Slot

from retroscope.services.config_store import ConfigStore

_COLORS = ["#EF9F27", "#85B7EB", "#ED93B1", "#7FC97F", "#BDB8D7"]


class BookmarkService(QObject):
    """Persists bookmarks in config as a list of positions."""

    bookmarks_changed = Signal(list)

    def __init__(
        self,
        config: ConfigStore,
        motion_ctrl,
        objective_mgr,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config  = config
        self._motion  = motion_ctrl
        self._obj     = objective_mgr

    # Internal helpers
    def _load(self) -> list[dict]:
        return list(self._config.get("ui.bookmarks", []))

    def _save(self, bms: list[dict]) -> None:
        self._config.set("ui.bookmarks", bms)
        self._config.save()
        self.bookmarks_changed.emit(bms)

    # Public API
    def bookmarks(self) -> list[dict]:
        return self._load()

    def save_current(self, name: str, x: int, y: int, z: int, objective: str) -> None:
        """Append a new bookmark with the given name and position."""
        bms = self._load()
        idx = len(bms) + 1
        color = _COLORS[(idx - 1) % len(_COLORS)]
        bms.append({
            "name":      name.strip() or f"Mark {idx}",
            "color":     color,
            "objective": objective,
            "x":         x,
            "y":         y,
            "z":         z,
        })
        self._save(bms)

    def delete(self, name: str) -> None:
        bms = [b for b in self._load() if b.get("name") != name]
        self._save(bms)

    def navigate_to(self, name: str, cur_x: int, cur_y: int, cur_z: int) -> None:
        """Move to the saved XYZ and switch objective."""
        bms = self._load()
        bm = next((b for b in bms if b.get("name") == name), None)
        if bm is None:
            return
        # Switch objective first so speed limits update before moving
        self._obj.set_active(bm["objective"])
        dx = int(bm["x"]) - cur_x
        dy = int(bm["y"]) - cur_y
        dz = int(bm["z"]) - cur_z
        if dx != 0 or dy != 0:
            if self._motion.move_rel(dx, dy, 0) is False:
                return
        if dz != 0:
            self._motion.move_z(dz)
