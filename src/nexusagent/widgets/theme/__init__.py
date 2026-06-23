"""Semantic color definitions and theme registry for NexusAgent TUI.

Inspired by Linear (dark-mode-first, near-black canvas, single accent color)
and DeepAgents (semantic CSS variables, theme registry).

Design principles:
- Near-black background (#11181C), not pure black
- Single accent color (indigo-violet #5E6AD2) used sparingly
- All other colors are grayscale with blue-cool undertone
- Borders are semi-transparent white, never solid dark
- Three-tier weight system: muted < primary < accent
"""

from nexusagent.widgets.theme.colors import (
    ALL_THEMES,
    DARK_COLORS,
    ROSE_PINE_COLORS,
    SOLARIZED_DARK_COLORS,
    THEME_REGISTRY,
    TOKYO_NIGHT_COLORS,
    ThemeColors,
)
from nexusagent.widgets.theme.registry import (
    get_css_variable_defaults,
    get_theme_colors,
    get_theme_css,
)

__all__ = [
    "ALL_THEMES",
    "DARK_COLORS",
    "ROSE_PINE_COLORS",
    "SOLARIZED_DARK_COLORS",
    "THEME_REGISTRY",
    "TOKYO_NIGHT_COLORS",
    "ThemeColors",
    "get_css_variable_defaults",
    "get_theme_colors",
    "get_theme_css",
    "register_themes",
]

# Import register_themes lazily to avoid circular imports
def register_themes(app):
    """Register NexusAgent themes with the Textual app."""
    from nexusagent.widgets.theme.registry import register_themes as _register
    return _register(app)
