"""Tests for SDK version handshake enhancements."""

import pytest


class TestSDKVersionConstants:
    """Tests for version constants in sdk.py."""

    def test_sdk_has_server_version(self):
        """sdk.py must export SERVER_VERSION constant."""
        from nexusagent.server.sdk import SERVER_VERSION
        assert isinstance(SERVER_VERSION, str)
        assert len(SERVER_VERSION) > 0

    def test_sdk_has_min_client_version(self):
        """sdk.py must export MIN_CLIENT_VERSION constant."""
        from nexusagent.server.sdk import MIN_CLIENT_VERSION
        assert isinstance(MIN_CLIENT_VERSION, str)
        assert len(MIN_CLIENT_VERSION) > 0

    def test_sdk_versions_match_module(self):
        """SDK constants must match version.VERSION."""
        from nexusagent.server.sdk import MIN_CLIENT_VERSION, SERVER_VERSION
        from nexusagent.version import VERSION
        assert SERVER_VERSION == VERSION
        assert MIN_CLIENT_VERSION == VERSION


class TestSDKHealthCheck:
    """Tests for enhanced health_check() with version."""

    @pytest.mark.asyncio
    async def test_health_check_includes_version(self):
        """health_check() must return version field."""
        from nexusagent.server.sdk import NexusSDK
        sdk = NexusSDK()
        result = await sdk.health_check()
        assert "version" in result
        assert "nats" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_health_check_version_matches(self):
        """health_check() version must match VERSION module."""
        from nexusagent.server.sdk import NexusSDK
        from nexusagent.version import VERSION
        sdk = NexusSDK()
        result = await sdk.health_check()
        assert result["version"] == VERSION
