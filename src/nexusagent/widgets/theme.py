"""Semantic color definitions for NexusAgent TUI.

Inspired by Linear (dark-mode-first, near-black canvas, single accent color)
and DeepAgents (semantic CSS variables, theme registry).

Design principles:
- Near-black background (#11181C), not pure black
- Single accent color (indigo-violet #5E6AD2) used sparingly
- All other colors are grayscale with blue-cool undertone
- Borders are semi-transparent white, never solid dark
- Three-tier weight system: muted < primary < accent
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

logger = logging.getLogger(__name__)


# ── Brand Palette (Linear-inspired, indigo accent) ────────────────────────

# Backgrounds — near-black with blue-cool undertone
BG = "#11181C"              # Main background
BG_PANEL = "#1A1D23"        # Panel/sidebar background
BG_SURFACE = "#23252A"      # Elevated surface (cards, inputs)
BG_HOVER = "#28282C"        # Hover state

# Text — grayscale with cool undertone
TEXT = "#F7F8F8"            # Primary text (not pure white)
TEXT_SECONDARY = "#D0D6E0"  # Body text, descriptions
TEXT_MUTED = "#8A8F98"      # Placeholders, metadata
TEXT_DIM = "#62666D"        # Timestamps, disabled

# Accent — indigo-violet (the ONLY chromatic color)
ACCENT = "#5E6AD2"          # Brand indigo — CTAs, active states
ACCENT_HOVER = "#7170FF"    # Brighter violet — hover states
ACCENT_LIGHT = "#828FFF"    # Lightest variant — subtle highlights

# Status — used sparingly
SUCCESS = "#10B981"         # Emerald green
WARNING = "#EB8B46"         # Amber
ERROR = "#F7768E"           # Soft pink-red
ERROR_BG = "#2A1F32"        # Subtle pink-tinted background

# Borders — semi-transparent white (the Linear way)
BORDER = "rgba(255,255,255,0.08)"       # Standard border
BORDER_SUBTLE = "rgba(255,255,255,0.05)" # Subtle border
BORDER_FOCUS = "#5E6AD2"                 # Focused border (accent color)


@dataclass(frozen=True)
class ThemeColors:
    """Semantic color tokens for a single theme (dark or light)."""
    # Backgrounds
    bg: str
    bg_panel: str
    bg_surface: str
    bg_hover: str

    # Text
    text: str
    text_secondary: str
    text_muted: str
    text_dim: str

    # Accent
    accent: str
    accent_hover: str
    accent_light: str

    # Status
    success: str
    warning: str
    error: str
    error_bg: str

    # Borders
    border: str
    border_subtle: str
    border_focus: str


# ── Dark Theme (default) ──────────────────────────────────────────────────

DARK_COLORS = ThemeColors(
    bg=BG,
    bg_panel=BG_PANEL,
    bg_surface=BG_SURFACE,
    bg_hover=BG_HOVER,
    text=TEXT,
    text_secondary=TEXT_SECONDARY,
    text_muted=TEXT_MUTED,
    text_dim=TEXT_DIM,
    accent=ACCENT,
    accent_hover=ACCENT_HOVER,
    accent_light=ACCENT_LIGHT,
    success=SUCCESS,
    warning=WARNING,
    error=ERROR,
    error_bg=ERROR_BG,
    border=BORDER,
    border_subtle=BORDER_SUBTLE,
    border_focus=BORDER_FOCUS,
)


def get_theme_colors() -> ThemeColors:
    """Return the active theme colors."""
    return DARK_COLORS


def get_css_variable_defaults() -> dict[str, str]:
    """Return CSS variable defaults for Textual theme registration.

    These map semantic tokens to Textual CSS variables.
    Reference in TCSS as: $primary, $background, $text-muted, etc.
    """
    c = DARK_COLORS
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
    }


def register_themes(app: "App") -> None:
    """Register NexusAgent themes with the Textual app."""
    from textual.theme import Theme

    colors = get_css_variable_defaults()

    # Dark theme (default)
    dark_theme = Theme(
        name="nexus-dark",
        variables=colors,
    )
    app.register_theme(dark_theme)

    # Catppuccin Mocha
    catppuccin = Theme(
        name="catppuccin-mocha",
        variables={
            "background": "#1E1E2E",
            "surface": "#181825",
            "primary": "#89B4FA",
            "secondary": "#CBA6F7",
            "success": "#A6E3A1",
            "warning": "#F9E2AF",
            "error": "#F38BA8",
            "text": "#CDD6F4",
            "text-muted": "#6C7086",
            "text-secondary": "#A6ADC8",
            "border": "rgba(255,255,255,0.08)",
            "border-subtle": "rgba(255,255,255,0.05)",
            "border-focus": "#89B4FA",
            "bg-surface": "#313244",
            "bg-hover": "#45475A",
            "error-muted": "#2A1F32",
            "accent-light": "#B4BEFE",
        },
    )
    app.register_theme(catppuccin)

    # Gruvbox Dark
    gruvbox = Theme(
        name="gruvbox-dark",
        variables={
            "background": "#282828",
            "surface": "#1D2021",
            "primary": "#458588",
            "secondary": "#B16286",
            "success": "#98971A",
            "warning": "#D79921",
            "error": "#CC241D",
            "text": "#EBDBB2",
            "text-muted": "#928374",
            "text-secondary": "#BDAE93",
            "border": "rgba(255,255,255,0.08)",
            "border-subtle": "rgba(255,255,255,0.05)",
            "border-focus": "#458588",
            "bg-surface": "#3C3836",
            "bg-hover": "#504945",
            "error-muted": "#3C1F1F",
            "accent-light": "#83A598",
        },
    )
    app.register_theme(gruvbox)

    # Nord
    nord = Theme(
        name="nord",
        variables={
            "background": "#2E3440",
            "surface": "#3B4252",
            "primary": "#5E81AC",
            "secondary": "#B48EAD",
            "success": "#A3BE8C",
            "warning": "#EBCB8B",
            "error": "#BF616A",
            "text": "#ECEFF4",
            "text-muted": "#7B88A1",
            "text-secondary": "#D8DEE9",
            "border": "rgba(255,255,255,0.08)",
            "border-subtle": "rgba(255,255,255,0.05)",
            "border-focus": "#5E81AC",
            "bg-surface": "#434C5E",
            "bg-hover": "#4C566A",
            "error-muted": "#3B2C2E",
            "accent-light": "#81A1C1",
        },
    )
    app.register_theme(nord)
