"""Tests for version comparison and compatibility logic."""



class TestParseVersion:
    """Tests for version string parsing."""

    def test_parse_simple_version(self):
        """Standard semver string parses correctly."""
        from nexusagent.interfaces.cli import parse_version
        assert parse_version("0.1.0") == (0, 1, 0)

    def test_parse_version_with_pre_release(self):
        """Pre-release suffix is stripped."""
        from nexusagent.interfaces.cli import parse_version
        assert parse_version("0.1.0-dev") == (0, 1, 0)
        assert parse_version("1.2.3-rc1") == (1, 2, 3)

    def test_parse_version_with_build_metadata(self):
        """Build metadata is stripped."""
        from nexusagent.interfaces.cli import parse_version
        assert parse_version("0.1.0+build.123") == (0, 1, 0)

    def test_parse_version_double_digit(self):
        """Multi-digit components parse correctly."""
        from nexusagent.interfaces.cli import parse_version
        assert parse_version("12.34.56") == (12, 34, 56)


class TestIsCompatible:
    """Tests for version compatibility checking."""

    def test_same_version_compatible(self):
        """Identical versions are compatible."""
        from nexusagent.interfaces.cli import is_compatible
        assert is_compatible("0.1.0", "0.1.0") is True

    def test_patch_difference_compatible(self):
        """Different patch versions are compatible."""
        from nexusagent.interfaces.cli import is_compatible
        assert is_compatible("0.1.0", "0.1.5") is True
        assert is_compatible("0.1.5", "0.1.0") is True

    def test_client_newer_compatible(self):
        """Client with higher minor version is compatible (can degrade)."""
        from nexusagent.interfaces.cli import is_compatible
        assert is_compatible("0.1.0", "0.2.0") is True

    def test_major_mismatch_incompatible(self):
        """Different major versions are incompatible."""
        from nexusagent.interfaces.cli import is_compatible
        assert is_compatible("0.1.0", "1.0.0") is False
        assert is_compatible("1.0.0", "0.1.0") is False

    def test_pre_release_compatible(self):
        """Pre-release versions with same base are compatible."""
        from nexusagent.interfaces.cli import is_compatible
        assert is_compatible("0.1.0", "0.2.0-dev") is True


class TestVersionSync:
    """Tests that version sources stay synchronized."""

    def test_all_sources_match(self):
        """VERSION file, version.py, server, and SDK must all match."""
        from importlib.metadata import version as pkg_version
        from pathlib import Path

        from nexusagent.server.sdk import SERVER_VERSION
        from nexusagent.version import VERSION

        # Read VERSION file
        version_file = Path(__file__).resolve().parent.parent / "VERSION"
        file_ver = version_file.read_text().strip()

        # All must match
        pkg_ver = pkg_version("nexusagent")
        assert pkg_ver == VERSION, f"version.py={VERSION} != pyproject={pkg_ver}"
        assert pkg_ver == SERVER_VERSION, f"sdk={SERVER_VERSION} != pyproject={pkg_ver}"
        assert file_ver == pkg_ver, f"VERSION={file_ver} != pyproject={pkg_ver}"
