"""Persistent JSON config store"""

import json
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

_CONFIG_DIR = Path.home() / ".config" / "retroscope"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "default_config.json"


class ConfigStore(QObject):
    config_changed = Signal(str)

    def __init__(self, parent: QObject | None = None, autosave_delay_ms: int = 500) -> None:
        super().__init__(parent)
        self._data: dict = {}
        self._dirty = False
        self._autosave_delay_ms = max(0, int(autosave_delay_ms))
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save)

    # Load / save
    def load(self) -> None:
        """Load config, merging with defaults on first run."""
        defaults = self._load_defaults()
        self._data = dict(defaults)

        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if _CONFIG_FILE.exists():
            try:
                with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                    user = json.load(f)
                self._deep_merge(self._data, user)
            except Exception:
                pass  # fall back to defaults

    def save(self) -> None:
        """Write config to disk."""
        if self._save_timer.isActive():
            self._save_timer.stop()
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CONFIG_FILE.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, _CONFIG_FILE)
            self._dirty = False
        except Exception:
            pass

    def flush(self) -> None:
        """Synchronously save any pending config changes."""
        self.save()

    # Access
    def get(self, key: str, default: Any = None) -> Any:
        """get('ui.dark_theme') -> self._data['ui']['dark_theme']."""
        node = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        if node.get(parts[-1]) == value:
            return
        node[parts[-1]] = value
        self._dirty = True
        self.config_changed.emit(key)
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if self._autosave_delay_ms <= 0:
            self.save()
            return
        self._save_timer.start(self._autosave_delay_ms)

    # Helpers
    def _load_defaults(self) -> dict:
        if _DEFAULT_CONFIG.exists():
            try:
                with open(_DEFAULT_CONFIG, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _deep_merge(self, base: dict, override: dict) -> None:
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v
