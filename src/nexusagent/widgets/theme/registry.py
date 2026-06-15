"""Theme registry and CSS variable generation for NexusAgent TUI."""

import logging
from typing import TYPE_CHECKING

from nexusagent.widgets.theme.colors import DARK_COLORS, THEME_REGISTRY

if TYPE_CHECKING:
    from textual.app import App

logger = logging.getLogger(__name__)


def get_theme_colors(theme_name: str = "nexus-dark"):
    """Return the ThemeColors for a given theme name."""
    return THEME_REGISTRY.get(theme_name, DARK_COLORS)


def get_theme_css(theme_name: str = "nexus-dark") -> dict[str, str]:
    """Return CSS variable dict for a specific theme."""
    c = THEME_REGISTRY.get(theme_name, DARK_COLORS)
    return {
        # Standard Textual variables
        "background": c.bg,
        "surface": c.bg_panel,
        "primary": c.accent,
        "secondary": c.accent_hover,
        "success": c.success,
        "warning": c.warning,
        "error": c.error,
        "text": c.text,
        "text-muted": c.text_muted,
        "text-secondary": c.text_secondary,
        # App-specific variables
        "border": c.border,
        "border-subtle": c.border_subtle,
        "border-focus": c.border_focus,
        "bg-surface": c.bg_surface,
        "bg-hover": c.bg_hover,
        "error-muted": c.error_bg,
        "accent-light": c.accent_light,
        # Extended semantic tokens (20+)
        "text-dim": c.text_dim,
        "accent-hover": c.accent_hover,
        "panel": c.bg_panel,
    }


def get_css_variable_defaults() -> dict[str, str]:
    """Return CSS variable defaults for Textual theme registration."""
    return get_theme_css("nexus-dark")


def register_themes(app: "App") -> None:
    """Register NexusAgent themes with the Textual app.

    Registers all 7 themes from THEME_REGISTRY:
    nexus-dark, tokyo-night, rose-pine, solarized-dark,
    catppuccin-mocha, gruvbox-dark, nord.
    """
    from textual.theme import Theme

    from nexusagent.widgets.theme.colors import ALL_THEMES

    for name in ALL_THEMES:
        colors = get_theme_colors(name)
        theme = Theme(primary=colors.accent, name=name, variables=get_theme_css(name))
        app.register_theme(theme)
        logger.debug(f"Registered theme: {name}")
