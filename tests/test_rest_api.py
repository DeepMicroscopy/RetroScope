"""Tests for the REST API.

Note: Partially AI-generated
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from retroscope.api.app import create_api_app
from retroscope.api.context import ApiContext
from retroscope.api.service import RestApiService
from retroscope.services import ome_tiff
from retroscope.services.image_store import ImageStore, META_KEY


class FakeConfig:
    def __init__(self, root: Path, values: dict[str, object] | None = None) -> None:
        self._root = root
        self._values = dict(values or {})

    def get(self, key: str, default=None):
        if key == "captures.root":
            return str(self._root)
        return self._values.get(key, default)


class ImmediateDispatcher:
    def call(self, func, timeout_s: float = 5.0):
        del timeout_s
        return func()


class FakeAutofocus:
    def __init__(self) -> None:
        self.busy = False
        self.cancelling = False
        self.starts = 0

    def start_autofocus(self) -> None:
        self.starts += 1
        self.busy = True


def _mk_ome(path: Path, *, captured_at: datetime, media_type: str = "snapshot") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.new("RGB", (32, 24), color="green"))
    ome_tiff.write_snapshot(
        path,
        rgb,
        {
            "version": 1,
            "type": media_type,
            "captured_at": captured_at.isoformat(timespec="seconds"),
            "objective": "20x",
            "position": {"x": 10, "y": 20, "z": 30},
            "width": 32,
            "height": 24,
            "format": "OME-TIFF",
            "tags": ["api"],
        },
    )
    if media_type != "snapshot":
        ImageStore.sidecar_path(path).write_text(
            json.dumps({META_KEY: {"type": media_type}}),
            encoding="utf-8",
        )


def _client(tmp_path: Path, autofocus: FakeAutofocus | None = None) -> tuple[TestClient, ImageStore]:
    store = ImageStore(FakeConfig(tmp_path / "captures"))
    context = ApiContext(
        image_store=store,
        autofocus_svc=autofocus or FakeAutofocus(),
        dispatcher=ImmediateDispatcher(),
    )
    return TestClient(create_api_app(context)), store


def test_openapi_and_docs_include_routes(tmp_path: Path) -> None:
    client, _store = _client(tmp_path)

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/captures" in paths
    assert "/api/v1/captures/{capture_id}/download" in paths
    assert "/api/v1/actions/autofocus" in paths

    assert client.get("/docs").status_code == 200


def test_capture_listing_filter_sort_limit_offset(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    now = datetime.now().replace(microsecond=0)
    old = now - timedelta(days=1)

    _mk_ome(store.snapshot_dir() / "old.ome.tiff", captured_at=old)
    _mk_ome(store.snapshot_dir() / "new.ome.tiff", captured_at=now)
    _mk_ome(store.stacks_dir() / "stack.ome.tiff", captured_at=now, media_type="stack")

    response = client.get("/api/v1/captures", params={
        "type": "snapshot",
        "sort": "oldest",
        "limit": 1,
        "offset": 1,
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert len(payload["captures"]) == 1
    assert payload["captures"][0]["filename"] == "new.ome.tiff"
    assert payload["captures"][0]["position"] == {"x": 10, "y": 20, "z": 30}
    assert payload["captures"][0]["download_url"].endswith("/download")


def test_capture_download_and_missing_id(tmp_path: Path) -> None:
    client, store = _client(tmp_path)
    _mk_ome(
        store.snapshot_dir() / "download.ome.tiff",
        captured_at=datetime.now().replace(microsecond=0),
    )

    listed = client.get("/api/v1/captures").json()["captures"]
    capture_id = listed[0]["id"]

    download = client.get(f"/api/v1/captures/{capture_id}/download")
    assert download.status_code == 200
    assert len(download.content) > 0
    assert "download.ome.tiff" in download.headers["content-disposition"]

    assert client.get("/api/v1/captures/not-a-real-id/download").status_code == 404


def test_autofocus_action_starts_once_and_reports_busy(tmp_path: Path) -> None:
    autofocus = FakeAutofocus()
    client, _store = _client(tmp_path, autofocus)

    started = client.post("/api/v1/actions/autofocus")
    assert started.status_code == 202
    assert started.json()["state"] == "started"
    assert autofocus.starts == 1

    busy = client.post("/api/v1/actions/autofocus")
    assert busy.status_code == 409
    assert busy.json()["state"] == "busy"
    assert autofocus.starts == 1


def test_rest_api_service_respects_disabled_config(tmp_path: Path) -> None:
    config = FakeConfig(tmp_path / "captures", {"api.enabled": False})
    svc = RestApiService(
        config,
        image_store=ImageStore(config),
        autofocus_svc=FakeAutofocus(),
        dispatcher=ImmediateDispatcher(),
    )

    svc.start()

    assert svc.running is False


def test_rest_api_service_skips_unavailable_port(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(RestApiService, "_port_available", lambda self, host, port: False)
    config = FakeConfig(tmp_path / "captures")
    svc = RestApiService(
        config,
        image_store=ImageStore(config),
        autofocus_svc=FakeAutofocus(),
        dispatcher=ImmediateDispatcher(),
    )

    svc.start()

    assert svc.running is False


def test_rest_api_service_start_and_stop(monkeypatch, tmp_path: Path) -> None:
    import retroscope.api.service as api_service_module

    class FakeServer:
        instances: list[FakeServer] = []

        def __init__(self, config) -> None:
            self.config = config
            self.should_exit = False
            self.started = threading.Event()
            FakeServer.instances.append(self)

        def run(self) -> None:
            self.started.set()
            while not self.should_exit:
                time.sleep(0.005)

    monkeypatch.setattr(api_service_module.uvicorn, "Server", FakeServer)
    monkeypatch.setattr(
        api_service_module.uvicorn,
        "Config",
        lambda app, host, port, log_level, access_log: SimpleNamespace(
            app=app,
            host=host,
            port=port,
            log_level=log_level,
            access_log=access_log,
        ),
    )
    monkeypatch.setattr(RestApiService, "_port_available", lambda self, host, port: True)

    config = FakeConfig(tmp_path / "captures")
    svc = RestApiService(
        config,
        image_store=ImageStore(config),
        autofocus_svc=FakeAutofocus(),
        dispatcher=ImmediateDispatcher(),
    )

    svc.start()
    server = FakeServer.instances[-1]
    assert server.started.wait(1.0)
    assert svc.running is True

    svc.stop()

    assert server.should_exit is True
    assert svc.running is False
