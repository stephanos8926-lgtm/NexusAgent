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


# ── Tokyo Night Palette ───────────────────────────────────────────────────

# Backgrounds — deep navy/indigo
TN_BG = "#1A1B26"              # Main background
TN_BG_PANEL = "#16161E"        # Panel/sidebar
TN_BG_SURFACE = "#24283B"      # Elevated surface
TN_BG_HOVER = "#2F3346"        # Hover state

# Text — cool blue-grays
TN_TEXT = "#C0CAF5"            # Primary text
TN_TEXT_SECONDARY = "#9AA5CE"  # Body text
TN_TEXT_MUTED = "#565F89"      # Placeholders
TN_TEXT_DIM = "#3B4261"        # Timestamps, disabled

# Accent — cyan-blue
TN_ACCENT = "#7AA2F7"          # Tokyo Night blue
TN_ACCENT_HOVER = "#89B4FF"    # Brighter blue
TN_ACCENT_LIGHT = "#B4D0FB"    # Lightest variant

# Status — neon-inspired
TN_SUCCESS = "#9ECE6A"         # Green
TN_WARNING = "#E0AF68"         # Gold
TN_ERROR = "#F7768E"           # Red-pink
TN_ERROR_BG = "#2D1F2F"        # Subtle red bg

# Borders — transparent white
TN_BORDER = "rgba(255,255,255,0.06)"
TN_BORDER_SUBTLE = "rgba(255,255,255,0.03)"
TN_BORDER_FOCUS = "#7AA2F7"


# ── Rosé Pine Palette ─────────────────────────────────────────────────────

# Backgrounds — warm dark pine
RP_BG = "#191724"              # Main background
RP_BG_PANEL = "#1F1D2E"        # Panel/sidebar
RP_BG_SURFACE = "#26233A"      # Elevated surface
RP_BG_HOVER = "#2D2A3F"        # Hover state

# Text — muted rose
RP_TEXT = "#E0DEF4"            # Primary text
RP_TEXT_SECONDARY = "#908CAA"  # Body text
RP_TEXT_MUTED = "#6E6A86"      # Placeholders
RP_TEXT_DIM = "#47445C"        # Timestamps, disabled

# Accent — dusty rose / iris
RP_ACCENT = "#C4A7E7"          # Iris/purple (Rosé Pine v2)
RP_ACCENT_HOVER = "#D0BFFF"    # Brighter iris
RP_ACCENT_LIGHT = "#EADFF9"    # Lightest variant

# Status — muted
RP_SUCCESS = "#31748F"         # Pine/teal
RP_WARNING = "#F6C177"         # Gold
RP_ERROR = "#EB6F92"           # Rose/love
RP_ERROR_BG = "#2D1F2F"        # Subtle rose bg

# Borders — very subtle
RP_BORDER = "rgba(255,255,255,0.05)"
RP_BORDER_SUBTLE = "rgba(255,255,255,0.02)"
RP_BORDER_FOCUS = "#C4A7E7"


# ── Solarized Dark Palette ────────────────────────────────────────────────

# Backgrounds — classic Solarized
SD_BG = "#002B36"              # Base03 — main background
SD_BG_PANEL = "#073642"        # Base02 — panels
SD_BG_SURFACE = "#0A4050"      # Slightly lighter
SD_BG_HOVER = "#0B4D5E"        # Hover state

# Text — warm grays
SD_TEXT = "#FDF6E3"            # Base3 — primary (warm white)
SD_TEXT_SECONDARY = "#EEE8D5"  # Base2 — body
SD_TEXT_MUTED = "#839496"      # Base0 — muted
SD_TEXT_DIM = "#657B83"        # Base00 — dim

# Accent — classic Solarized blue
SD_ACCENT = "#268BD2"          # Blue
SD_ACCENT_HOVER = "#3AA1E2"    # Brighter blue
SD_ACCENT_LIGHT = "#69B7E8"    # Light blue

# Status — Solarized palette
SD_SUCCESS = "#859900"         # Green
SD_WARNING = "#B58900"         # Yellow
SD_ERROR = "#DC322F"           # Red
SD_ERROR_BG = "#2F1A1A"        # Subtle red bg

# Borders — subtle
SD_BORDER = "rgba(255,255,255,0.07)"
SD_BORDER_SUBTLE = "rgba(255,255,255,0.04)"
SD_BORDER_FOCUS = "#268BD2"


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


# ── Tokyo Night Theme ─────────────────────────────────────────────────────

TOKYO_NIGHT_COLORS = ThemeColors(
    bg=TN_BG,
    bg_panel=TN_BG_PANEL,
    bg_surface=TN_BG_SURFACE,
    bg_hover=TN_BG_HOVER,
    text=TN_TEXT,
    text_secondary=TN_TEXT_SECONDARY,
    text_muted=TN_TEXT_MUTED,
    text_dim=TN_TEXT_DIM,
    accent=TN_ACCENT,
    accent_hover=TN_ACCENT_HOVER,
    accent_light=TN_ACCENT_LIGHT,
    success=TN_SUCCESS,
    warning=TN_WARNING,
    error=TN_ERROR,
    error_bg=TN_ERROR_BG,
    border=TN_BORDER,
    border_subtle=TN_BORDER_SUBTLE,
    border_focus=TN_BORDER_FOCUS,
)


# ── Rosé Pine Theme ───────────────────────────────────────────────────────

ROSE_PINE_COLORS = ThemeColors(
    bg=RP_BG,
    bg_panel=RP_BG_PANEL,
    bg_surface=RP_BG_SURFACE,
    bg_hover=RP_BG_HOVER,
    text=RP_TEXT,
    text_secondary=RP_TEXT_SECONDARY,
    text_muted=RP_TEXT_MUTED,
    text_dim=RP_TEXT_DIM,
    accent=RP_ACCENT,
    accent_hover=RP_ACCENT_HOVER,
    accent_light=RP_ACCENT_LIGHT,
    success=RP_SUCCESS,
    warning=RP_WARNING,
    error=RP_ERROR,
    error_bg=RP_ERROR_BG,
    border=RP_BORDER,
    border_subtle=RP_BORDER_SUBTLE,
    border_focus=RP_BORDER_FOCUS,
)


# ── Solarized Dark Theme ──────────────────────────────────────────────────

SOLARIZED_DARK_COLORS = ThemeColors(
    bg=SD_BG,
    bg_panel=SD_BG_PANEL,
    bg_surface=SD_BG_SURFACE,
    bg_hover=SD_BG_HOVER,
    text=SD_TEXT,
    text_secondary=SD_TEXT_SECONDARY,
    text_muted=SD_TEXT_MUTED,
    text_dim=SD_TEXT_DIM,
    accent=SD_ACCENT,
    accent_hover=SD_ACCENT_HOVER,
    accent_light=SD_ACCENT_LIGHT,
    success=SD_SUCCESS,
    warning=SD_WARNING,
    error=SD_ERROR,
    error_bg=SD_ERROR_BG,
    border=SD_BORDER,
    border_subtle=SD_BORDER_SUBTLE,
    border_focus=SD_BORDER_FOCUS,
)


# ── Theme Registry ────────────────────────────────────────────────────────

THEME_REGISTRY: dict[str, ThemeColors] = {
    "nexus-dark": DARK_COLORS,
    "tokyo-night": TOKYO_NIGHT_COLORS,
    "rose-pine": ROSE_PINE_COLORS,
    "solarized-dark": SOLARIZED_DARK_COLORS,
    "catppuccin-mocha": ThemeColors(
        bg="#1E1E2E", bg_panel="#181825", bg_surface="#313244",
        bg_hover="#45475A", text="#CDD6F4", text_secondary="#A6ADC8",
        text_muted="#6C7086", text_dim="#4C5066", accent="#89B4FA",
        accent_hover="#B4BEFE", accent_light="#D9E2F0",
        success="#A6E3A1", warning="#F9E2AF", error="#F38BA8",
        error_bg="#2A1F32", border="rgba(255,255,255,0.08)",
        border_subtle="rgba(255,255,255,0.05)", border_focus="#89B4FA",
    ),
    "gruvbox-dark": ThemeColors(
        bg="#282828", bg_panel="#1D2021", bg_surface="#3C3836",
        bg_hover="#504945", text="#EBDBB2", text_secondary="#BDAE93",
        text_muted="#928374", text_dim="#7C6F64", accent="#458588",
        accent_hover="#83A598", accent_light="#8EC07C",
        success="#98971A", warning="#D79921", error="#CC241D",
        error_bg="#3C1F1F", border="rgba(255,255,255,0.08)",
        border_subtle="rgba(255,255,255,0.05)", border_focus="#458588",
    ),
    "nord": ThemeColors(
        bg="#2E3440", bg_panel="#3B4252", bg_surface="#434C5E",
        bg_hover="#4C566A", text="#ECEFF4", text_secondary="#D8DEE9",
        text_muted="#7B88A1", text_dim="#5E6779", accent="#5E81AC",
        accent_hover="#81A1C1", accent_light="#88C0D0",
        success="#A3BE8C", warning="#EBCB8B", error="#BF616A",
        error_bg="#3B2C2E", border="rgba(255,255,255,0.08)",
        border_subtle="rgba(255,255,255,0.05)", border_focus="#5E81AC",
    ),
}

ALL_THEMES: list[str] = list(THEME_REGISTRY.keys())


def get_theme_colors(theme_name: str = "nexus-dark") -> ThemeColors:
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
    """Return CSS variable defaults for Textual theme registration.

    These map semantic tokens to Textual CSS variables.
    Reference in TCSS as: $primary, $background, $text-muted, etc.
    """
    return get_theme_css("nexus-dark")


def register_themes(app: "App") -> None:
    """Register NexusAgent themes with the Textual app.

    Registers all 7 themes:
    - nexus-dark (default), tokyo-night, rose-pine, solarized-dark
    - catppuccin-mocha, gruvbox-dark, nord
    """
    from textual.theme import Theme

    # Register all themes from the registry (4 built-in)
    for name, colors in THEME_REGISTRY.items():
        theme = Theme(name=name, variables=get_theme_css(name))
        app.register_theme(theme)

    # Catppuccin Mocha
    app.register_theme(Theme(
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
    ))

    # Gruvbox Dark
    app.register_theme(Theme(
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
    ))

    # Nord
    app.register_theme(Theme(
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
    ))
