"""Background Uvicorn service for REST API."""

from __future__ import annotations

import logging
import socket
import threading
from typing import Any

import uvicorn

from retroscope.api.app import create_api_app
from retroscope.api.context import ApiContext

logger = logging.getLogger(__name__)


class RestApiService:
    def __init__(
        self,
        config,
        *,
        image_store,
        autofocus_svc,
        dispatcher,
    ) -> None:
        self._config = config
        self._context = ApiContext(
            image_store=image_store,
            autofocus_svc=autofocus_svc,
            dispatcher=dispatcher,
        )
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running or not self._config_bool("api.enabled", True):
            return

        host = str(self._config_get("api.host", "0.0.0.0") or "0.0.0.0")
        port = self._config_int("api.port", 8765)
        docs_enabled = self._config_bool("api.docs_enabled", True)

        if not self._port_available(host, port):
            logger.warning("[api] REST API port unavailable: %s:%d", host, port)
            return

        app = create_api_app(self._context, docs_enabled=docs_enabled)
        uvicorn_config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=False,
        )
        self._server = uvicorn.Server(uvicorn_config)
        self._thread = threading.Thread(
            target=self._run_server,
            name="RetroScope REST API",
            daemon=True,
        )
        self._thread.start()
        logger.info("[api] REST API starting on http://%s:%d", host, port)

    def stop(self) -> None:
        server = self._server
        if server is not None:
            server.should_exit = True

        thread = self._thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=3.0)

        self._thread = None
        self._server = None

    def _run_server(self) -> None:
        server = self._server
        if server is None:
            return
        try:
            server.run()
        except Exception:
            logger.exception("[api] REST API server stopped unexpectedly")

    def _config_get(self, key: str, default: Any) -> Any:
        if self._config is None or not hasattr(self._config, "get"):
            return default
        return self._config.get(key, default)

    def _config_bool(self, key: str, default: bool) -> bool:
        return bool(self._config_get(key, default))

    def _config_int(self, key: str, default: int) -> int:
        try:
            return int(self._config_get(key, default))
        except (TypeError, ValueError):
            return default

    def _port_available(self, host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, port))
                return True
        except OSError:
            return False
