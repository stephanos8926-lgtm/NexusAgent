"""Semantic color definitions for NexusAgent TUI.

This module is a compatibility shim. The actual implementations live in:
- ``nexusagent.widgets.theme.colors`` — color palettes + ThemeColors dataclass
- ``nexusagent.widgets.theme.registry`` — theme registry + CSS generation

All public symbols are re-exported here for backward compatibility.
"""

from nexusagent.widgets.theme.colors import (
    ALL_THEMES,
    DARK_COLORS,
    ROSE_PINE_COLORS,
    SOLARIZED_DARK_COLORS,
    TOKYO_NIGHT_COLORS,
    THEME_REGISTRY,
    ThemeColors,
)
from nexusagent.widgets.theme.registry import (
    get_css_variable_defaults,
    get_theme_colors,
    get_theme_css,
    register_themes,
)

__all__ = [
    "ThemeColors",
    "DARK_COLORS",
    "TOKYO_NIGHT_COLORS",
    "ROSE_PINE_COLORS",
    "SOLARIZED_DARK_COLORS",
    "THEME_REGISTRY",
    "ALL_THEMES",
    "get_theme_colors",
    "get_theme_css",
    "get_css_variable_defaults",
    "register_themes",
]
