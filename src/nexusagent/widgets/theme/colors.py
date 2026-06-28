"""Color palette definitions and theme data for NexusAgent TUI."""

from dataclasses import dataclass

# ── Brand Palette (Linear-inspired, indigo accent) ────────────────────────

# Backgrounds — near-black with blue-cool undertone
BG = "#11181C"  # Main background
BG_PANEL = "#1A1D23"  # Panel/sidebar background
BG_SURFACE = "#23252A"  # Elevated surface (cards, inputs)
BG_HOVER = "#28282C"  # Hover state

# Text — grayscale with cool undertone
TEXT = "#F7F8F8"  # Primary text (not pure white)
TEXT_SECONDARY = "#D0D6E0"  # Body text, descriptions
TEXT_MUTED = "#8A8F98"  # Placeholders, metadata
TEXT_DIM = "#62666D"  # Timestamps, disabled

# Accent — indigo-violet (the ONLY chromatic color)
ACCENT = "#5E6AD2"  # Brand indigo — CTAs, active states
ACCENT_HOVER = "#7170FF"  # Brighter violet — hover states
ACCENT_LIGHT = "#828FFF"  # Lightest variant — subtle highlights

# Status — used sparingly
SUCCESS = "#10B981"  # Emerald green
WARNING = "#EB8B46"  # Amber
ERROR = "#F7768E"  # Soft pink-red
ERROR_BG = "#2A1F32"  # Subtle pink-tinted background

# Borders — semi-transparent white (the Linear way)
BORDER = "rgba(255,255,255,0.08)"  # Standard border
BORDER_SUBTLE = "rgba(255,255,255,0.05)"  # Subtle border
BORDER_FOCUS = "#5E6AD2"  # Focused border (accent color)


# ── Tokyo Night Palette ───────────────────────────────────────────────────

TN_BG = "#1A1B26"
TN_BG_PANEL = "#16161E"
TN_BG_SURFACE = "#24283B"
TN_BG_HOVER = "#2F3346"
TN_TEXT = "#C0CAF5"
TN_TEXT_SECONDARY = "#9AA5CE"
TN_TEXT_MUTED = "#565F89"
TN_TEXT_DIM = "#3B4261"
TN_ACCENT = "#7AA2F7"
TN_ACCENT_HOVER = "#89B4FF"
TN_ACCENT_LIGHT = "#B4D0FB"
TN_SUCCESS = "#9ECE6A"
TN_WARNING = "#E0AF68"
TN_ERROR = "#F7768E"
TN_ERROR_BG = "#2D1F2F"
TN_BORDER = "rgba(255,255,255,0.06)"
TN_BORDER_SUBTLE = "rgba(255,255,255,0.03)"
TN_BORDER_FOCUS = "#7AA2F7"


# ── Rosé Pine Palette ─────────────────────────────────────────────────────

RP_BG = "#191724"
RP_BG_PANEL = "#1F1D2E"
RP_BG_SURFACE = "#26233A"
RP_BG_HOVER = "#2D2A3F"
RP_TEXT = "#E0DEF4"
RP_TEXT_SECONDARY = "#908CAA"
RP_TEXT_MUTED = "#6E6A86"
RP_TEXT_DIM = "#47445C"
RP_ACCENT = "#C4A7E7"
RP_ACCENT_HOVER = "#D0BFFF"
RP_ACCENT_LIGHT = "#EADFF9"
RP_SUCCESS = "#31748F"
RP_WARNING = "#F6C177"
RP_ERROR = "#EB6F92"
RP_ERROR_BG = "#2D1F2F"
RP_BORDER = "rgba(255,255,255,0.05)"
RP_BORDER_SUBTLE = "rgba(255,255,255,0.02)"
RP_BORDER_FOCUS = "#C4A7E7"


# ── Solarized Dark Palette ────────────────────────────────────────────────

SD_BG = "#002B36"
SD_BG_PANEL = "#073642"
SD_BG_SURFACE = "#0A4050"
SD_BG_HOVER = "#0B4D5E"
SD_TEXT = "#FDF6E3"
SD_TEXT_SECONDARY = "#EEE8D5"
SD_TEXT_MUTED = "#839496"
SD_TEXT_DIM = "#657B83"
SD_ACCENT = "#268BD2"
SD_ACCENT_HOVER = "#3AA1E2"
SD_ACCENT_LIGHT = "#69B7E8"
SD_SUCCESS = "#859900"
SD_WARNING = "#B58900"
SD_ERROR = "#DC322F"
SD_ERROR_BG = "#2F1A1A"
SD_BORDER = "rgba(255,255,255,0.07)"
SD_BORDER_SUBTLE = "rgba(255,255,255,0.04)"
SD_BORDER_FOCUS = "#268BD2"


# ── Catppuccin Mocha ──────────────────────────────────────────────────────

CP_BG = "#1E1E2E"
CP_BG_PANEL = "#181825"
CP_BG_SURFACE = "#313244"
CP_BG_HOVER = "#45475A"
CP_TEXT = "#CDD6F4"
CP_TEXT_SECONDARY = "#A6ADC8"
CP_TEXT_MUTED = "#6C7086"
CP_TEXT_DIM = "#4C5066"
CP_ACCENT = "#89B4FA"
CP_ACCENT_HOVER = "#B4BEFE"
CP_ACCENT_LIGHT = "#D9E2F0"
CP_SUCCESS = "#A6E3A1"
CP_WARNING = "#F9E2AF"
CP_ERROR = "#F38BA8"
CP_ERROR_BG = "#2A1F32"
CP_BORDER = "rgba(255,255,255,0.08)"
CP_BORDER_SUBTLE = "rgba(255,255,255,0.05)"
CP_BORDER_FOCUS = "#89B4FA"


# ── Gruvbox Dark ──────────────────────────────────────────────────────────

GB_BG = "#282828"
GB_BG_PANEL = "#1D2021"
GB_BG_SURFACE = "#3C3836"
GB_BG_HOVER = "#504945"
GB_TEXT = "#EBDBB2"
GB_TEXT_SECONDARY = "#BDAE93"
GB_TEXT_MUTED = "#928374"
GB_TEXT_DIM = "#7C6F64"
GB_ACCENT = "#458588"
GB_ACCENT_HOVER = "#83A598"
GB_ACCENT_LIGHT = "#8EC07C"
GB_SUCCESS = "#98971A"
GB_WARNING = "#D79921"
GB_ERROR = "#CC241D"
GB_ERROR_BG = "#3C1F1F"
GB_BORDER = "rgba(255,255,255,0.08)"
GB_BORDER_SUBTLE = "rgba(255,255,255,0.05)"
GB_BORDER_FOCUS = "#458588"


# ── Nord ──────────────────────────────────────────────────────────────────

ND_BG = "#2E3440"
ND_BG_PANEL = "#3B4252"
ND_BG_SURFACE = "#434C5E"
ND_BG_HOVER = "#4C566A"
ND_TEXT = "#ECEFF4"
ND_TEXT_SECONDARY = "#D8DEE9"
ND_TEXT_MUTED = "#7B88A1"
ND_TEXT_DIM = "#5E6779"
ND_ACCENT = "#5E81AC"
ND_ACCENT_HOVER = "#81A1C1"
ND_ACCENT_LIGHT = "#88C0D0"
ND_SUCCESS = "#A3BE8C"
ND_WARNING = "#EBCB8B"
ND_ERROR = "#BF616A"
ND_ERROR_BG = "#3B2C2E"
ND_BORDER = "rgba(255,255,255,0.08)"
ND_BORDER_SUBTLE = "rgba(255,255,255,0.05)"
ND_BORDER_FOCUS = "#5E81AC"


# ── ThemeColors Dataclass ─────────────────────────────────────────────────


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


# ── Theme Instances ───────────────────────────────────────────────────────

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

CATPPUCCIN_MOCHA_COLORS = ThemeColors(
    bg=CP_BG,
    bg_panel=CP_BG_PANEL,
    bg_surface=CP_BG_SURFACE,
    bg_hover=CP_BG_HOVER,
    text=CP_TEXT,
    text_secondary=CP_TEXT_SECONDARY,
    text_muted=CP_TEXT_MUTED,
    text_dim=CP_TEXT_DIM,
    accent=CP_ACCENT,
    accent_hover=CP_ACCENT_HOVER,
    accent_light=CP_ACCENT_LIGHT,
    success=CP_SUCCESS,
    warning=CP_WARNING,
    error=CP_ERROR,
    error_bg=CP_ERROR_BG,
    border=CP_BORDER,
    border_subtle=CP_BORDER_SUBTLE,
    border_focus=CP_BORDER_FOCUS,
)

GRUVBOX_DARK_COLORS = ThemeColors(
    bg=GB_BG,
    bg_panel=GB_BG_PANEL,
    bg_surface=GB_BG_SURFACE,
    bg_hover=GB_BG_HOVER,
    text=GB_TEXT,
    text_secondary=GB_TEXT_SECONDARY,
    text_muted=GB_TEXT_MUTED,
    text_dim=GB_TEXT_DIM,
    accent=GB_ACCENT,
    accent_hover=GB_ACCENT_HOVER,
    accent_light=GB_ACCENT_LIGHT,
    success=GB_SUCCESS,
    warning=GB_WARNING,
    error=GB_ERROR,
    error_bg=GB_ERROR_BG,
    border=GB_BORDER,
    border_subtle=GB_BORDER_SUBTLE,
    border_focus=GB_BORDER_FOCUS,
)

NORD_COLORS = ThemeColors(
    bg=ND_BG,
    bg_panel=ND_BG_PANEL,
    bg_surface=ND_BG_SURFACE,
    bg_hover=ND_BG_HOVER,
    text=ND_TEXT,
    text_secondary=ND_TEXT_SECONDARY,
    text_muted=ND_TEXT_MUTED,
    text_dim=ND_TEXT_DIM,
    accent=ND_ACCENT,
    accent_hover=ND_ACCENT_HOVER,
    accent_light=ND_ACCENT_LIGHT,
    success=ND_SUCCESS,
    warning=ND_WARNING,
    error=ND_ERROR,
    error_bg=ND_ERROR_BG,
    border=ND_BORDER,
    border_subtle=ND_BORDER_SUBTLE,
    border_focus=ND_BORDER_FOCUS,
)

# ── Theme Registry ────────────────────────────────────────────────────────

THEME_REGISTRY: dict[str, ThemeColors] = {
    "nexus-dark": DARK_COLORS,
    "tokyo-night": TOKYO_NIGHT_COLORS,
    "rose-pine": ROSE_PINE_COLORS,
    "solarized-dark": SOLARIZED_DARK_COLORS,
    "catppuccin-mocha": CATPPUCCIN_MOCHA_COLORS,
    "gruvbox-dark": GRUVBOX_DARK_COLORS,
    "nord": NORD_COLORS,
}

ALL_THEMES: list[str] = list(THEME_REGISTRY.keys())
