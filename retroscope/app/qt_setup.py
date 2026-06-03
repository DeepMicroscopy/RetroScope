"""Qt and platform bootstrap helpers."""

from __future__ import annotations

import functools
import os
import sys
from pathlib import Path

APP_ICON_PATH = Path(__file__).resolve().parents[1] / "qml" / "icons" / "app_icon.png"

def force_mock_platform() -> None:
    """Force mock drivers."""
    import retroscope.platform as platform

    platform.get_platform.cache_clear()
    platform.get_platform = functools.cache(lambda: "mac")

def create_application(scale: float = 1.0):
    """Create and configure the QApplication."""
    
    # QT virtual keyboard
    os.environ.setdefault("QT_IM_MODULE", "qtvirtualkeyboard")

    if scale != 1.0:
        os.environ["QT_SCALE_FACTOR"] = str(scale)

    # Suppress multimedia codec logging to keep logs clean
    extra_rules = [
        "qt.multimedia.playbackengine.codec=false",
        "qt.multimedia.ffmpeg*=false",
        "qt.qml.propertyCache.append=false",
        "qt.qpa.fonts=false",
        "qt.qpa.wayland.warning=false",
    ]
    existing = os.environ.get("QT_LOGGING_RULES", "")
    current_rules = [rule.strip() for rule in existing.split(";") if rule.strip()]
    for rule in extra_rules:
        if rule not in current_rules:
            current_rules.append(rule)
    if current_rules:
        os.environ["QT_LOGGING_RULES"] = ";".join(current_rules)

    from PySide6.QtCore import QLoggingCategory, Qt
    from PySide6.QtGui import QFont, QFontDatabase, QIcon
    from PySide6.QtWidgets import QApplication

    if current_rules:
        QLoggingCategory.setFilterRules("\n".join(current_rules))

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    if app.font().family() not in QFontDatabase.families():
        for family in ("Helvetica Neue", "Arial"):
            if family in QFontDatabase.families():
                app.setFont(QFont(family))
                break
    app.setApplicationName("RetroScope")
    app.setOrganizationName("RetroScope")
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    return app
