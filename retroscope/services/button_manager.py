"""Button manager: Maps physical GPIO buttons to configurable actions."""

import time

from PySide6.QtCore import QObject, Signal, Slot

from retroscope.services.config_store import ConfigStore

NUM_BUTTONS = 4
DEFAULT_MAPPING = ["none"] * NUM_BUTTONS
_STARTUP_SUPPRESS_S = 1.5

class ActionDefinition:
    def __init__(self, action_id: str, label: str, callback) -> None:
        self.action_id = action_id
        self.label = label
        self.callback = callback

class ButtonManager(QObject):
    """Listens to button_pressed events and dispatches registered actions."""

    action_executed = Signal(int, str)  # (button_index, action_id)

    def __init__(
        self,
        buttons_driver,
        config: ConfigStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._actions: dict[str, ActionDefinition] = {}
        self._suppressed_until = time.monotonic() + _STARTUP_SUPPRESS_S
        self._mapping: list[str] = list(
            config.get("buttons.mapping", DEFAULT_MAPPING)
        )

        while len(self._mapping) < NUM_BUTTONS:
            self._mapping.append("none")
        self._mapping = self._mapping[:NUM_BUTTONS]

        self.register_action("none", "- None -", lambda: None)

        buttons_driver.button_pressed.connect(self.on_button_pressed)

    # Action registry
    def register_action(self, action_id: str, label: str, callback) -> None:
        """Register a callable action. Call during app startup to populate the menu."""
        self._actions[action_id] = ActionDefinition(action_id, label, callback)

    def available_actions(self) -> list[ActionDefinition]:
        """Ordered list for UI dropdowns."""
        # "none" always first, rest alphabetical by label
        result = [self._actions["none"]]
        result += sorted(
            [a for k, a in self._actions.items() if k != "none"],
            key=lambda a: a.label,
        )
        return result

    # Mapping
    def get_mapping(self) -> list[str]:
        return list(self._mapping)

    def set_action(self, button_index: int, action_id: str) -> None:
        """Assign an action to a button and persist to config."""
        if not 0 <= button_index < NUM_BUTTONS:
            return
        self._mapping[button_index] = action_id
        self._config.set("buttons.mapping", list(self._mapping))

    def suppress_for(self, seconds: float) -> None:
        """Ignore hardware button edges during noisy device-change windows."""
        self._suppressed_until = max(
            self._suppressed_until,
            time.monotonic() + max(0.0, seconds),
        )

    # Dispatch
    @Slot(int)
    def on_button_pressed(self, index: int) -> None:
        if not 0 <= index < NUM_BUTTONS:
            return
        if time.monotonic() < self._suppressed_until:
            return
        action_id = self._mapping[index]
        action = self._actions.get(action_id)
        if action is not None:
            try:
                action.callback()
            except Exception:
                pass
        self.action_executed.emit(index, action_id)
