"""API ids for gallery captures."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def capture_api_id(path: str | Path) -> str:
    resolved = str(Path(path).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def capture_api_id_from_item(item: dict[str, Any]) -> str:
    return capture_api_id(str(item.get("path", "")))
