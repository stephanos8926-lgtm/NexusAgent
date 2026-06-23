"""Tests for server /version endpoint and version constant."""

import pytest


class TestVersionConstant:
    """Tests for src.nexusagent.version single source of truth."""

    def test_version_file_exists(self):
        """VERSION file must exist at project root."""
        from pathlib import Path
        version_file = Path(__file__).resolve().parent.parent / "VERSION"
        assert version_file.exists(), f"VERSION file not found at {version_file}"

    def test_version_file_matches_pyproject(self):
        """VERSION file must match pyproject.toml version."""
        from importlib.metadata import version as pkg_version
        from pathlib import Path
        version_file = Path(__file__).resolve().parent.parent / "VERSION"
        file_ver = version_file.read_text().strip()
        pkg_ver = pkg_version("nexusagent")
        assert file_ver == pkg_ver, f"VERSION={file_ver} != pyproject={pkg_ver}"

    def test_version_module_exists(self):
        """src.nexusagent.version module must exist with VERSION constant."""
        from nexusagent.version import VERSION
        assert isinstance(VERSION, str)
        assert len(VERSION) > 0

    def test_version_module_matches_pyproject(self):
        """version.VERSION must match pyproject.toml."""
        from importlib.metadata import version as pkg_version

        from nexusagent.version import VERSION
        assert pkg_version("nexusagent") == VERSION


class TestServerVersionEndpoint:
    """Tests for GET /version endpoint."""

    @pytest.fixture
    def client(self):
        """Create a TestClient for the FastAPI app."""
        from fastapi.testclient import TestClient

        # Import after version module is created to avoid import errors
        from nexusagent.server.server import app
        return TestClient(app)

    def test_version_endpoint_exists(self, client):
        """GET /version must return 200."""
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_has_required_fields(self, client):
        """Response must include version, minClient, server."""
        response = client.get("/version")
        data = response.json()
        assert "version" in data
        assert "minClient" in data
        assert "server" in data
        assert data["server"] == "nexus-server"

    def test_version_matches_module(self, client):
        """Response version must match version.VERSION."""
        from nexusagent.version import VERSION
        response = client.get("/version")
        data = response.json()
        assert data["version"] == VERSION


class TestServerHealthEnhancement:
    """Tests for enhanced /health endpoint with version."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from nexusagent.server.server import app
        return TestClient(app)

    def test_health_includes_version(self, client):
        """GET /health must include version field."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "nats" in data
