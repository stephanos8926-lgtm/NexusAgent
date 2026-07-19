"""Tests for the server lifespan adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestServerLifespan:
    """Server lifespan adapter with Runtime."""

    @patch("nexusagent.server.lifespan.Runtime")
    @patch("nexusagent.core.worker.NexusWorker", autospec=True)
    @patch("nexusagent.server.lifespan.settings.server.api_port", 18022)
    async def test_create_server_app(self, mock_runtime_cls, mock_nexus_worker):
        """create_server_app() produces a working FastAPI app."""
        from nexusagent.server.lifespan import create_server_app

        mock_runtime = MagicMock()
        mock_runtime.initialize = AsyncMock()
        mock_runtime.shutdown = AsyncMock()
        mock_runtime.state.name = "RUNNING"
        mock_runtime_cls.return_value = mock_runtime

        app = create_server_app()
        assert app.title == "NexusAgent API"
        assert app.state is not None
