"""Button bridge: Exposes button mapping configuration to QML."""

from PySide6.QtCore import Property, QObject, Signal, Slot

from retroscope.services.button_manager import ButtonManager


class ButtonBridge(QObject):
    mapping_changed = Signal()
    actions_changed = Signal()
    button_pressed = Signal(int)  # button index

    def __init__(self, manager: ButtonManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mgr = manager
        manager.action_executed.connect(lambda idx, _: self.button_pressed.emit(idx))
        if hasattr(manager, "mapping_changed"):
            manager.mapping_changed.connect(self.mapping_changed)

    @Property(list, notify=mapping_changed)
    def mappingModel(self) -> list:
        """Current action for each button."""
        return self._mgr.get_mapping()

    @Property(list, notify=actions_changed)
    def availableActionIds(self) -> list:
        return [a.action_id for a in self._mgr.available_actions()]

    @Property(list, notify=actions_changed)
    def availableActionLabels(self) -> list:
        return [a.label for a in self._mgr.available_actions()]

    @Slot(int, str)
    def setAction(self, button_index: int, action_id: str) -> None:
        self._mgr.set_action(button_index, action_id)
