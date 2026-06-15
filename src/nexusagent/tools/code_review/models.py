"""Code review data models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ─── Severity Levels ────────────────────────────────────────────────────

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
SEVERITY_INFO = "INFO"

_SEVERITY_ORDER = {
    SEVERITY_CRITICAL: 0,
    SEVERITY_HIGH: 1,
    SEVERITY_MEDIUM: 2,
    SEVERITY_LOW: 3,
    SEVERITY_INFO: 4,
}

_SEVERITY_ICON = {
    SEVERITY_CRITICAL: "🔴",
    SEVERITY_HIGH: "🟠",
    SEVERITY_MEDIUM: "🟡",
    SEVERITY_LOW: "🔵",
    SEVERITY_INFO: "ℹ️",  # noqa: RUF001
}


# ─── Issue Model ────────────────────────────────────────────────────────


@dataclass
class Issue:
    """A single code review finding."""

    severity: str
    category: str  # "security", "bug", "style", "performance", "maintainability"
    message: str
    line: int | None = None
    suggestion: str = ""

    def format(self) -> str:
        """Format the issue as a human-readable string with severity icon.

        Returns:
            Formatted string with severity, category, message, line number,
            and optional suggestion.
        """
        icon = _SEVERITY_ICON.get(self.severity, "•")
        line_info = f" (line {self.line})" if self.line else ""
        suggestion = f"\n    → Suggestion: {self.suggestion}" if self.suggestion else ""
        return f"  {icon} [{self.severity}] [{self.category}]{line_info}: {self.message}{suggestion}"


@dataclass
class ReviewResult:
    """Complete code review result."""

    issues: list[Issue] = field(default_factory=list)
    summary: str = ""
    lines_reviewed: int = 0

    def add(self, severity, category, message, line=None, suggestion=""):
        """Add a new issue to the review result."""
        self.issues.append(Issue(severity, category, message, line, suggestion))

    def sort_issues(self):
        """Sort issues by severity (critical first, info last)."""
        self.issues.sort(key=lambda i: _SEVERITY_ORDER.get(i.severity, 99))

    def format_report(self) -> str:
        """Generate the full formatted review report.

        Groups issues by category, appends a severity summary,
        and returns the complete report string.
        """
        self.sort_issues()
        lines = [f"# Code Review Report ({self.lines_reviewed} lines reviewed)\n"]

        if not self.issues:
            lines.append("✅ No issues found. Code looks clean!")
            return "\n".join(lines)

        # Group by category
        by_cat: dict[str, list[Issue]] = {}
        for issue in self.issues:
            by_cat.setdefault(issue.category, []).append(issue)

        for cat in sorted(by_cat.keys()):
            lines.append(f"\n## {cat.upper()} ({len(by_cat[cat])})")
            for issue in by_cat[cat]:
                lines.append(issue.format())

        # Summary
        critical = sum(1 for i in self.issues if i.severity == SEVERITY_CRITICAL)
        high = sum(1 for i in self.issues if i.severity == SEVERITY_HIGH)
        medium = sum(1 for i in self.issues if i.severity == SEVERITY_MEDIUM)
        low = sum(1 for i in self.issues if i.severity in (SEVERITY_LOW, SEVERITY_INFO))

        lines.append("\n## Summary")
        lines.append(f"  Total issues: {len(self.issues)}")
        if critical:
            lines.append(f"  🔴 Critical: {critical}")
        if high:
            lines.append(f"  🟠 High: {high}")
        if medium:
            lines.append(f"  🟡 Medium: {medium}")
        if low:
            lines.append(f"  🔵 Low/Info: {low}")

        return "\n".join(lines)
