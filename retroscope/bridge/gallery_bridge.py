"""Gallery bridge: Exposes capture gallery (from filesystem) to QML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from retroscope.services import ome_tiff
from retroscope.services.image_store import ImageStore

FILTER_OPTIONS = ["all", "snapshot", "video", "stack", "stitch"]
TYPE_LABELS = {
    "snapshot": "Capture",
    "video": "Video",
    "stack": "Stack",
    "stitch": "Scan",
}

def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"

def _format_group_label(dt: datetime) -> str:
    today = datetime.now().date()
    if dt.date() == today:
        return f"Today, {dt.day} {dt.strftime('%B %Y')}"
    return f"{dt.day} {dt.strftime('%B %Y')}"

class GalleryBridge(QObject):
    """QML gallery model and actions."""

    items_changed = Signal()
    grouped_changed = Signal()
    selected_changed = Signal()
    filter_changed = Signal()
    sort_changed = Signal()
    view_changed = Signal()
    summary_changed = Signal()
    action_message = Signal(str)

    def __init__(
        self,
        store: ImageStore,
        motion_ctrl,
        objective_mgr,
        get_position: Callable[[], tuple[int, int, int]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._motion = motion_ctrl
        self._objective = objective_mgr
        self._get_position = get_position

        self._filter_type = "all"
        self._sort_order = "newest"
        self._view_mode = "grid"
        self._all_items: list[dict] = []
        self._visible_items: list[dict] = []
        self._grouped_items: list[dict] = []
        self._selected_id = ""
        self.refresh()
        QTimer.singleShot(0, self.refresh)


    # QML properties
    @Property(list, notify=items_changed)
    def items(self) -> list:
        return self._visible_items

    @Property(list, notify=grouped_changed)
    def groupedItems(self) -> list:
        return self._grouped_items

    @Property(int, notify=selected_changed)
    def selectedIndex(self) -> int:
        for i, item in enumerate(self._visible_items):
            if item.get("id") == self._selected_id:
                return i
        return -1

    @Property(str, notify=selected_changed)
    def selectedId(self) -> str:
        return self._selected_id

    @Property("QVariantMap", notify=selected_changed)
    def selectedItem(self) -> dict:
        for item in self._visible_items:
            if item.get("id") == self._selected_id:
                return item
        return {}

    @Property(list, constant=True)
    def filterOptions(self) -> list:
        return list(FILTER_OPTIONS)

    @Property(str, notify=filter_changed)
    def filterType(self) -> str:
        return self._filter_type

    @Property(str, notify=sort_changed)
    def sortOrder(self) -> str:
        return self._sort_order

    @Property(str, notify=view_changed)
    def viewMode(self) -> str:
        return self._view_mode

    @Property(int, notify=summary_changed)
    def captureCount(self) -> int:
        return len(self._visible_items)

    @Property(str, notify=summary_changed)
    def totalSizeLabel(self) -> str:
        total = sum(int(item.get("file_size", 0)) for item in self._visible_items)
        return _format_size(total)


    # Slots
    @Slot()
    def refresh(self) -> None:
        current = self._selected_id
        self._all_items = self._store.scan_items()
        self._rebuild(current)

    @Slot(str)
    def on_capture_saved(self, _path: str) -> None:
        self.refresh()

    @Slot(str)
    def setFilterType(self, value: str) -> None:
        if value not in FILTER_OPTIONS or value == self._filter_type:
            return
        self._filter_type = value
        self.filter_changed.emit()
        self._rebuild(self._selected_id)

    @Slot(str)
    def setSortOrder(self, value: str) -> None:
        if value not in {"newest", "oldest"} or value == self._sort_order:
            return
        self._sort_order = value
        self.sort_changed.emit()
        self._rebuild(self._selected_id)

    @Slot(str)
    def setViewMode(self, value: str) -> None:
        if value not in {"grid", "list"} or value == self._view_mode:
            return
        self._view_mode = value
        self.view_changed.emit()

    @Slot(int)
    def selectIndex(self, index: int) -> None:
        if index < 0 or index >= len(self._visible_items):
            return
        item_id = str(self._visible_items[index].get("id", ""))
        if item_id == self._selected_id:
            return
        self._selected_id = item_id
        self.selected_changed.emit()

    @Slot(int)
    def selectByIndex(self, index: int) -> None:
        self.selectIndex(index)

    @Slot(str)
    def selectItem(self, item_id: str) -> None:
        if item_id == "" or item_id == self._selected_id:
            return
        if any(item.get("id") == item_id for item in self._visible_items):
            self._selected_id = item_id
            self.selected_changed.emit()

    @Slot(str)
    def addTag(self, tag: str) -> None:
        clean = tag.strip()
        if clean == "":
            return
        item = self.selectedItem
        if not item:
            return
        tags = list(item.get("tags", []))
        if clean in tags:
            return
        tags.append(clean)
        if self._store.persist_tags(Path(item["path"]), tags):
            self.refresh()

    @Slot(str)
    def removeTag(self, tag: str) -> None:
        clean = tag.strip()
        if clean == "":
            return
        item = self.selectedItem
        if not item:
            return
        tags = [t for t in item.get("tags", []) if t != clean]
        if self._store.persist_tags(Path(item["path"]), tags):
            self.refresh()

    @Slot()
    def deleteSelected(self) -> None:
        item = self.selectedItem
        if not item:
            return
        path = Path(item["path"])
        if self._store.delete_item(path):
            self.action_message.emit("Capture deleted")
            self.refresh()

    @Slot()
    def goToSelectedPosition(self) -> None:
        item = self.selectedItem
        if not item:
            return

        tx = item.get("pos_x")
        ty = item.get("pos_y")
        tz = item.get("pos_z")
        if tx is None or ty is None or tz is None:
            self.action_message.emit("No saved stage position")
            return

        objective = str(item.get("objective", "")).strip()
        if objective != "":
            self._objective.set_active(objective)

        cx, cy, cz = self._get_position()
        dx = int(tx) - int(cx)
        dy = int(ty) - int(cy)
        dz = int(tz) - int(cz)

        if dx != 0 or dy != 0:
            if self._motion.move_rel(dx, dy, 0) is False:
                return
        if dz != 0:
            self._motion.move_z(dz)

        self.action_message.emit("Moving to saved position")


    # Rebuilding gallery items based on current filter/sort settings and preserving selection (if possible)
    def _rebuild(self, selected_id: str) -> None:
        items = [
            it for it in self._all_items
            if self._filter_type == "all" or it.get("type") == self._filter_type
        ]

        reverse = self._sort_order == "newest"
        items.sort(
            key=lambda it: (
                float(it.get("captured_ts", 0.0)),
                float(it.get("mtime_ts", 0.0)),
                str(it.get("filename", "")),
            ),
            reverse=reverse,
        )

        grouped: list[dict] = []
        flat: list[dict] = []
        grouped_index: dict[str, int] = {}

        for raw in items:
            captured = datetime.fromisoformat(str(raw["captured_at"]))
            group_key = captured.date().isoformat()
            group_label = _format_group_label(captured)
            display = self._to_display_item(raw, group_key, group_label)

            if group_key not in grouped_index:
                grouped_index[group_key] = len(grouped)
                grouped.append({"key": group_key, "label": group_label, "items": []})
            grouped[grouped_index[group_key]]["items"].append(display)
            flat.append(display)

        self._grouped_items = grouped
        self._visible_items = flat

        if selected_id and any(item.get("id") == selected_id for item in flat):
            self._selected_id = selected_id
        elif flat:
            self._selected_id = str(flat[0].get("id", ""))
        else:
            self._selected_id = ""

        self.grouped_changed.emit()
        self.items_changed.emit()
        self.summary_changed.emit()
        self.selected_changed.emit()

    def _to_display_item(self, raw: dict, group_key: str, group_label: str) -> dict:
        dt = datetime.fromisoformat(str(raw["captured_at"]))
        width = int(raw.get("width", 0) or 0)
        height = int(raw.get("height", 0) or 0)
        objective = str(raw.get("objective", "") or "")
        is_ome = ome_tiff.is_ome_tiff(Path(raw["path"]))
        if is_ome:
            file_url = ome_tiff.ome_image_url(raw["path"], 0, dt.timestamp())
            preview_url = file_url
            frames = [
                ome_tiff.ome_image_url(raw["path"], int(p.get("ifd", 0)), dt.timestamp())
                for p in raw.get("frames", [])
                if isinstance(p, dict)
            ]
            tiles = [
                ome_tiff.ome_image_url(raw["path"], int(p.get("ifd", 0)), dt.timestamp())
                for p in raw.get("tiles", [])
                if isinstance(p, dict)
            ]
        else:
            file_url = QUrl.fromLocalFile(raw["path"]).toString()
            preview_url = (
                QUrl.fromLocalFile(raw.get("preview_path", raw["path"])).toString()
                if str(raw.get("preview_path", "")).strip() != ""
                else ""
            )
            frames = list(raw.get("frames", []))
            tiles = list(raw.get("tiles", []))

        return {
            "itemId": raw["id"],
            "id": raw["id"],
            "path": raw["path"],
            "fileUrl": file_url,
            "playbackUrl": QUrl.fromLocalFile(raw.get("playback_path", raw["path"])).toString()
                           if str(raw.get("playback_path", "")).strip() != ""
                           else "",
            "previewUrl": preview_url,
            "filename": raw["filename"],
            "type": raw["type"],
            "typeLabel": TYPE_LABELS.get(str(raw["type"]), str(raw["type"]).title()),
            "capturedAt": raw["captured_at"],
            "dateLabel": dt.strftime("%-d %b %Y"),
            "timeLabel": dt.strftime("%H:%M"),
            "groupKey": group_key,
            "groupLabel": group_label,
            "objective": objective,
            "objectiveLabel": objective if objective != "" else "n/a",
            "resolution": f"{width} x {height}" if width > 0 and height > 0 else "n/a",
            "fileSize": _format_size(int(raw.get("file_size", 0))),
            "file_size": int(raw.get("file_size", 0)),
            "format": str(raw.get("format", "")),
            "pos_x": raw.get("pos_x"),
            "pos_y": raw.get("pos_y"),
            "pos_z": raw.get("pos_z"),
            "tags": list(raw.get("tags", [])),
            "isVideo": raw.get("type") == "video",
            "frames": frames,
            "tiles": tiles,
            "zHalfRange": raw.get("metadata", {}).get("z_half_range"),
            "stepSize": int(raw.get("metadata", {}).get("step_size", 0) or 0),
        }
