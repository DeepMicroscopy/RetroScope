"""BookmarkBridge: Exposes BookmarkService to QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.bookmark_service import BookmarkService


class BookmarkBridge(QObject):
    bookmarks_changed = Signal(list)

    def __init__(
        self,
        service: BookmarkService,
        motion_bridge,
        objective_bridge,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._svc     = service
        self._motion  = motion_bridge
        self._obj     = objective_bridge
        self._list: list = service.bookmarks()

        service.bookmarks_changed.connect(self._on_changed)

    def _on_changed(self, bms: list) -> None:
        self._list = bms
        self.bookmarks_changed.emit(bms)

    @Property(list, notify=bookmarks_changed)
    def bookmarkList(self) -> list:
        return self._list

    @Slot(str)
    def saveCurrent(self, name: str) -> None:
        self._svc.save_current(
            name,
            self._motion.posX,
            self._motion.posY,
            self._motion.posZ,
            self._obj.activeObjective,
        )

    @Slot(str)
    def deleteBM(self, name: str) -> None:
        self._svc.delete(name)

    @Slot(str)
    def navigateTo(self, name: str) -> None:
        self._svc.navigate_to(
            name,
            self._motion.posX,
            self._motion.posY,
            self._motion.posZ,
        )
