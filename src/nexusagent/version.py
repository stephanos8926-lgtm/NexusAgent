"""Single source of truth for NexusAgent version.

This module reads the version from pyproject.toml at runtime via importlib.metadata.
The VERSION file is validated against this at test time.
"""

from importlib.metadata import version as _pkg_version

VERSION: str = _pkg_version("nexusagent")
MIN_CLIENT_VERSION: str = VERSION
