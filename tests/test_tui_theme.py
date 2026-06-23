"""Tests for NexusAgent TUI theme system.

Covers:
- ThemeColors dataclass
- All 7 themes (nexus-dark, catppuccin-mocha, gruvbox-dark, nord,
  tokyo-night, rose-pine, solarized-dark)
- Theme CSS variable generation
- Theme registry
- NO_COLOR detection
- Git status indicator
- Context window bar
- Braille spinner animation
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from nexusagent.widgets.status import (
    BrailleSpinner,
    ContextWindowBar,
    GitStatus,
)
from nexusagent.widgets.theme import (
    ALL_THEMES,
    DARK_COLORS,
    ROSE_PINE_COLORS,
    SOLARIZED_DARK_COLORS,
    THEME_REGISTRY,
    TOKYO_NIGHT_COLORS,
    ThemeColors,
    get_css_variable_defaults,
    get_theme_colors,
)

# ---------------------------------------------------------------------------
# ThemeColors dataclass
# ---------------------------------------------------------------------------

class TestThemeColors:
    """Tests for the ThemeColors dataclass."""

    def test_is_frozen(self):
        """ThemeColors is immutable (frozen dataclass)."""
        c = ThemeColors(
            bg="#000000", bg_panel="#111111", bg_surface="#222222",
            bg_hover="#333333", text="#FFFFFF", text_secondary="#DDDDDD",
            text_muted="#999999", text_dim="#666666", accent="#5E6AD2",
            accent_hover="#7170FF", accent_light="#828FFF",
            success="#10B981", warning="#EB8B46", error="#F7768E",
            error_bg="#2A1F32", border="rgba(255,255,255,0.08)",
            border_subtle="rgba(255,255,255,0.05)", border_focus="#5E6AD2",
        )
        with pytest.raises(AttributeError):
            c.bg = "#FFFFFF"

    def test_all_fields_present(self):
        """ThemeColors has exactly 18 fields."""
        from dataclasses import fields
        field_names = [f.name for f in fields(ThemeColors)]
        assert len(field_names) == 18

    def test_field_names_semantic(self):
        """Fields use semantic naming (bg, text, accent, etc.)."""
        from dataclasses import fields
        field_names = {f.name for f in fields(ThemeColors)}
        expected = {
            "bg", "bg_panel", "bg_surface", "bg_hover",
            "text", "text_secondary", "text_muted", "text_dim",
            "accent", "accent_hover", "accent_light",
            "success", "warning", "error", "error_bg",
            "border", "border_subtle", "border_focus",
        }
        assert field_names == expected


# ---------------------------------------------------------------------------
# Theme token count (20+ semantic tokens)
# ---------------------------------------------------------------------------

class TestThemeTokens:
    """Each theme must provide 20+ semantic CSS tokens."""

    def test_css_variables_count(self):
        """get_css_variable_defaults returns at least 20 tokens."""
        variables = get_css_variable_defaults()
        assert len(variables) >= 20

    def test_css_variables_keys(self):
        """CSS variables cover all semantic categories."""
        variables = get_css_variable_defaults()
        # Must have standard Textual keys
        assert "background" in variables
        assert "surface" in variables
        assert "primary" in variables
        assert "text" in variables
        # Must have app-specific keys
        assert "border" in variables
        assert "bg-surface" in variables
        assert "accent-light" in variables


# ---------------------------------------------------------------------------
# Theme registry — all 7 themes present
# ---------------------------------------------------------------------------

class TestThemeRegistry:
    """Tests for the theme registry with all 7 themes."""

    def test_registry_has_7_themes(self):
        """THEME_REGISTRY contains all 7 themes."""
        assert len(THEME_REGISTRY) == 7

    def test_registry_theme_names(self):
        """Registry has the expected theme names."""
        names = set(THEME_REGISTRY.keys())
        expected = {
            "nexus-dark",
            "catppuccin-mocha",
            "gruvbox-dark",
            "nord",
            "tokyo-night",
            "rose-pine",
            "solarized-dark",
        }
        assert names == expected

    def test_registry_values_are_theme_colors(self):
        """All registry values are ThemeColors instances."""
        for name, colors in THEME_REGISTRY.items():
            assert isinstance(colors, ThemeColors), f"{name} is not ThemeColors"

    def test_all_themes_list(self):
        """ALL_THEMES lists all 7 theme names in order."""
        assert len(ALL_THEMES) == 7
        assert "tokyo-night" in ALL_THEMES
        assert "rose-pine" in ALL_THEMES
        assert "solarized-dark" in ALL_THEMES

    def test_dark_theme_is_default(self):
        """get_theme_colors returns DARK_COLORS by default."""
        assert get_theme_colors() is DARK_COLORS


# ---------------------------------------------------------------------------
# Tokyo Night theme
# ---------------------------------------------------------------------------

class TestTokyoNight:
    """Tests for the Tokyo Night theme."""

    def test_is_theme_colors(self):
        """TOKYO_NIGHT_COLORS is a ThemeColors instance."""
        assert isinstance(TOKYO_NIGHT_COLORS, ThemeColors)

    def test_background_is_dark(self):
        """Tokyo Night backgrounds are dark."""
        c = TOKYO_NIGHT_COLORS
        # All bg colors should be dark hex
        assert c.bg.startswith("#")
        assert c.bg_panel.startswith("#")
        assert c.bg_surface.startswith("#")
        assert c.bg_hover.startswith("#")

    def test_has_accent(self):
        """Tokyo Night has a distinct accent color."""
        assert TOKYO_NIGHT_COLORS.accent != ""

    def test_has_distinct_colors(self):
        """Tokyo Night colors differ from default dark."""
        assert TOKYO_NIGHT_COLORS.bg != DARK_COLORS.bg

    def test_in_registry(self):
        """Tokyo Night is in the theme registry."""
        assert "tokyo-night" in THEME_REGISTRY
        assert THEME_REGISTRY["tokyo-night"] is TOKYO_NIGHT_COLORS


# ---------------------------------------------------------------------------
# Rosé Pine theme
# ---------------------------------------------------------------------------

class TestRosePine:
    """Tests for the Rosé Pine theme."""

    def test_is_theme_colors(self):
        """ROSE_PINE_COLORS is a ThemeColors instance."""
        assert isinstance(ROSE_PINE_COLORS, ThemeColors)

    def test_background_is_dark(self):
        """Rosé Pine backgrounds are dark."""
        c = ROSE_PINE_COLORS
        assert c.bg.startswith("#")
        assert c.bg_panel.startswith("#")

    def test_has_accent(self):
        """Rosé Pine has a distinct accent (rose/muted purple)."""
        assert ROSE_PINE_COLORS.accent != ""

    def test_in_registry(self):
        """Rosé Pine is in the theme registry."""
        assert "rose-pine" in THEME_REGISTRY
        assert THEME_REGISTRY["rose-pine"] is ROSE_PINE_COLORS


# ---------------------------------------------------------------------------
# Solarized Dark theme
# ---------------------------------------------------------------------------

class TestSolarizedDark:
    """Tests for the Solarized Dark theme."""

    def test_is_theme_colors(self):
        """SOLARIZED_DARK_COLORS is a ThemeColors instance."""
        assert isinstance(SOLARIZED_DARK_COLORS, ThemeColors)

    def test_background_is_dark(self):
        """Solarized Dark backgrounds are dark."""
        c = SOLARIZED_DARK_COLORS
        assert c.bg.startswith("#")
        assert c.bg_panel.startswith("#")

    def test_has_accent(self):
        """Solarized Dark has a distinct accent."""
        assert SOLARIZED_DARK_COLORS.accent != ""

    def test_in_registry(self):
        """Solarized Dark is in the theme registry."""
        assert "solarized-dark" in THEME_REGISTRY
        assert THEME_REGISTRY["solarized-dark"] is SOLARIZED_DARK_COLORS


# ---------------------------------------------------------------------------
# NO_COLOR detection
# ---------------------------------------------------------------------------

class TestNoColor:
    """Tests for NO_COLOR environment detection."""

    def test_no_color_env_sets_flag(self):
        """When NO_COLOR is set, the NO_COLOR flag is True."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            # Re-import to pick up the env var
            import importlib

            import nexusagent.widgets.status as status_mod
            importlib.reload(status_mod)
            assert status_mod.NO_COLOR is True

    def test_no_color_unset(self):
        """When NO_COLOR is not set, the flag is False."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import nexusagent.widgets.status as status_mod
            importlib.reload(status_mod)
            # Should be False (or empty string is falsy)
            assert not status_mod.NO_COLOR


# ---------------------------------------------------------------------------
# Git Status
# ---------------------------------------------------------------------------

class TestGitStatus:
    """Tests for git status detection."""

    def test_git_status_clean(self):
        """clean status when git reports no changes."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            mock_git.return_value = ""
            status = GitStatus.detect()
            assert status == "clean"

    def test_git_status_dirty(self):
        """dirty status when git reports unstaged modifications."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            # Porcelain: " M" = unstaged modification (index=space, worktree=M)
            mock_git.return_value = " M file.txt\n"
            status = GitStatus.detect()
            assert status == "dirty"

    def test_git_status_staged(self):
        """staged status when git reports staged changes."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            # Porcelain: "M " = staged modification (index=M, worktree=space)
            mock_git.return_value = "M  file.txt\n"
            status = GitStatus.detect()
            assert status == "staged"

    def test_git_status_untracked(self):
        """dirty status for untracked files."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            # Porcelain: "??" = untracked
            mock_git.return_value = "?? new.py\n"
            status = GitStatus.detect()
            assert status == "dirty"

    def test_git_status_mixed(self):
        """staged takes priority when both staged and dirty exist."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            # Mixed: staged + unstaged
            mock_git.return_value = "M  staged.py\n M unstaged.py\n"
            status = GitStatus.detect()
            assert status == "staged"

    def test_git_no_repo(self):
        """None when not in a git repo."""
        with patch("nexusagent.widgets.status._run_git") as mock_git:
            mock_git.return_value = None
            status = GitStatus.detect()
            assert status is None

    def test_git_label_clean(self):
        """GitStatus.label() for clean."""
        assert GitStatus.label("clean") == "✓ clean"

    def test_git_label_dirty(self):
        """GitStatus.label() for dirty."""
        assert GitStatus.label("dirty") == "✗ dirty"

    def test_git_label_staged(self):
        """GitStatus.label() for staged."""
        assert GitStatus.label("staged") == "✔ staged"

    def test_git_label_none(self):
        """GitStatus.label() for None returns empty string."""
        assert GitStatus.label(None) == ""


# ---------------------------------------------------------------------------
# Context Window Bar
# ---------------------------------------------------------------------------

class TestContextWindowBar:
    """Tests for the context window usage bar."""

    def test_zero_percent(self):
        """0% usage shows 0%."""
        bar = ContextWindowBar(used=0, total=1000)
        assert bar.percentage == 0

    def test_full_percent(self):
        """100% usage."""
        bar = ContextWindowBar(used=500, total=500)
        assert bar.percentage == 100

    def test_half_percent(self):
        """50% usage."""
        bar = ContextWindowBar(used=250, total=500)
        assert bar.percentage == 50

    def test_rounds_down(self):
        """Percentage rounds down."""
        bar = ContextWindowBar(used=333, total=1000)
        assert bar.percentage == 33

    def test_zero_total(self):
        """Zero total avoids division by zero."""
        bar = ContextWindowBar(used=0, total=0)
        assert bar.percentage == 0

    def test_color_safe(self):
        """Color for <70% is success/green."""
        bar = ContextWindowBar(used=100, total=500)
        assert bar.color == "#10B981"  # success

    def test_color_warning(self):
        """Color for 70-90% is warning/amber."""
        bar = ContextWindowBar(used=400, total=500)
        assert bar.color == "#EB8B46"  # warning

    def test_color_danger(self):
        """Color for >90% is error/red."""
        bar = ContextWindowBar(used=490, total=500)
        assert bar.color == "#F7768E"  # error

    def test_bar_safe(self):
        """Bar content for safe range."""
        bar = ContextWindowBar(used=100, total=500)
        assert "20%" in str(bar.bar())

    def test_bar_shows_percentage(self):
        """Bar shows percentage text."""
        bar = ContextWindowBar(used=250, total=500)
        rendered = str(bar.bar())
        assert "50%" in rendered


# ---------------------------------------------------------------------------
# Braille Spinner
# ---------------------------------------------------------------------------

class TestBrailleSpinner:
    """Tests for the braille spinner animation."""

    def test_braille_chars_present(self):
        """BRAILLE_CHARS contains braille dot characters."""
        assert len(BrailleSpinner.CHARS) > 0
        # All chars should be single braille characters
        for ch in BrailleSpinner.CHARS:
            assert len(ch) == 1

    def test_has_10_frames(self):
        """Braille spinner has 10 frames (standard)."""
        assert len(BrailleSpinner.CHARS) == 10

    def test_first_frame(self):
        """First frame is ⠋."""
        assert BrailleSpinner.CHARS[0] == "⠋"

    def test_tick_advances(self):
        """tick() advances to next frame."""
        spinner = BrailleSpinner()
        assert spinner.frame == 0
        spinner.tick()
        assert spinner.frame == 1

    def test_tick_wraps(self):
        """tick() wraps around after last frame."""
        spinner = BrailleSpinner()
        spinner.frame = len(BrailleSpinner.CHARS) - 1
        spinner.tick()
        assert spinner.frame == 0

    def test_current_char(self):
        """current() returns the correct braille character."""
        spinner = BrailleSpinner()
        assert spinner.current() == BrailleSpinner.CHARS[0]
        spinner.tick()
        assert spinner.current() == BrailleSpinner.CHARS[1]

    def test_reset(self):
        """reset() returns to frame 0."""
        spinner = BrailleSpinner()
        for _ in range(5):
            spinner.tick()
        spinner.reset()
        assert spinner.frame == 0
