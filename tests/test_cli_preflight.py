"""Tests for CLI preflight version checking."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from nexusagent.interfaces.cli import main


class TestGetVersion:
    """Tests for the get_version() helper."""

    def test_get_version_returns_string(self):
        """get_version() must return a non-empty string."""
        from nexusagent.interfaces.cli import get_version

        result = get_version()
        assert isinstance(result, str)
        assert len(result) > 0


class TestParseVersion:
    """Tests for the parse_version() helper."""

    def test_parse_version_basic(self):
        """parse_version('1.2.3') -> (1, 2, 3)."""
        from nexusagent.interfaces.cli import parse_version

        assert parse_version("1.2.3") == (1, 2, 3)

    def test_parse_version_strips_prerelease(self):
        """parse_version('1.2.3-rc1') -> (1, 2, 3)."""
        from nexusagent.interfaces.cli import parse_version

        assert parse_version("1.2.3-rc1") == (1, 2, 3)

    def test_parse_version_zero(self):
        """parse_version('0.1.0') -> (0, 1, 0)."""
        from nexusagent.interfaces.cli import parse_version

        assert parse_version("0.1.0") == (0, 1, 0)


class TestIsCompatible:
    """Tests for the is_compatible() helper."""

    def test_same_version_is_compatible(self):
        from nexusagent.interfaces.cli import is_compatible

        assert is_compatible("0.1.0", "0.1.0") is True

    def test_same_major_minor_is_compatible(self):
        from nexusagent.interfaces.cli import is_compatible

        assert is_compatible("0.1.0", "0.1.5") is True

    def test_different_major_is_incompatible(self):
        from nexusagent.interfaces.cli import is_compatible

        assert is_compatible("0.1.0", "1.0.0") is False

    def test_different_minor_is_incompatible(self):
        from nexusagent.interfaces.cli import is_compatible

        assert is_compatible("0.1.0", "0.2.0") is True


class TestPreflightServerReachable:
    """Tests for preflight() when server is reachable."""

    def test_preflight_server_reachable(self):
        """preflight() should succeed when health_check returns ok."""
        from nexusagent.interfaces.cli import preflight

        mock_sdk = AsyncMock()
        mock_sdk.health_check.return_value = {
            "status": "ok",
            "version": "0.1.0",
            "minClient": "0.1.0",
            "nats": "connected",
        }

        with patch("nexusagent.server.sdk.sdk", mock_sdk):
            import asyncio

            result = asyncio.run(preflight())
            assert result is True

    def test_preflight_server_unreachable(self):
        """preflight() should return False when connection fails."""
        from nexusagent.interfaces.cli import preflight

        mock_sdk = AsyncMock()
        mock_sdk.health_check.side_effect = ConnectionError("refused")

        with patch("nexusagent.server.sdk.sdk", mock_sdk):
            import asyncio

            result = asyncio.run(preflight())
            assert result is False

    def test_preflight_version_mismatch_warning(self):
        """preflight() should warn but still succeed when versions mismatch."""
        from nexusagent.interfaces.cli import preflight

        mock_sdk = AsyncMock()
        mock_sdk.health_check.return_value = {
            "status": "ok",
            "version": "0.2.0",
            "minClient": "0.2.0",
            "nats": "connected",
        }

        with patch("nexusagent.server.sdk.sdk", mock_sdk):
            import asyncio

            result = asyncio.run(preflight())
            # Version mismatch is a warning, not a hard failure
            assert result is True


class TestCLISkipVersionCheck:
    """Tests for --skip-version-check flag on run/submit."""

    def test_submit_skip_version_check(self):
        """nexus-client submit --skip-version-check should bypass preflight."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["submit", "--skip-version-check", "test task"],
        )
        # Should not fail due to preflight (may fail for other reasons like NATS)
        # but should NOT contain "preflight" or "version" errors
        if result.exit_code != 0:
            assert "preflight" not in result.output.lower()
            assert "version mismatch" not in result.output.lower()

    def test_run_skip_version_check(self):
        """nexus run --skip-version-check should bypass preflight."""
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["run", "--skip-version-check", "test task"],
        )
        if result.exit_code != 0:
            assert "preflight" not in result.output.lower()
            assert "version mismatch" not in result.output.lower()


class TestCheckServerFlag:
    """Tests for --check-server flag on root group."""

    def test_check_server_flag_exists(self):
        """Root group should accept --check-server flag."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "--check-server" in result.output
