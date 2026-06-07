from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication

from retroscope.services.system_service import SystemService


def _app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class ConfigStub:
    def __init__(self, values=None) -> None:
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def save(self) -> None:
        pass


def test_system_bridge_exposes_api_urls_for_lan_host(monkeypatch) -> None:
    _app()
    import retroscope.bridge.system_bridge as system_bridge
    from retroscope.bridge.system_bridge import SystemBridge

    monkeypatch.setattr(system_bridge, "_current_ip_address", lambda: "192.168.1.23")
    cfg = ConfigStub({
        "api.enabled": True,
        "api.host": "0.0.0.0",
        "api.port": 9876,
        "api.docs_enabled": True,
    })

    bridge = SystemBridge(SystemService(cfg))

    assert bridge.currentIpAddress == "192.168.1.23"
    assert bridge.apiBaseUrl == "http://192.168.1.23:9876"
    assert bridge.apiDocsUrl == "http://192.168.1.23:9876/docs"


def test_system_bridge_marks_api_urls_disabled(monkeypatch) -> None:
    _app()
    import retroscope.bridge.system_bridge as system_bridge
    from retroscope.bridge.system_bridge import SystemBridge

    monkeypatch.setattr(system_bridge, "_current_ip_address", lambda: "192.168.1.23")
    cfg = ConfigStub({
        "api.enabled": False,
        "api.host": "0.0.0.0",
        "api.port": 9876,
        "api.docs_enabled": False,
    })

    bridge = SystemBridge(SystemService(cfg))

    assert bridge.apiBaseUrl == "Disabled"
    assert bridge.apiDocsUrl == "Disabled"
