"""Main code review orchestrator."""

from __future__ import annotations

from nexusagent.tools.code_review.checks.ast_check import check as _check_python_ast
from nexusagent.tools.code_review.checks.bugs import check as _check_bugs
from nexusagent.tools.code_review.checks.performance import check as _check_performance

# Import check functions directly from their modules to avoid circular imports
from nexusagent.tools.code_review.checks.security import check as _check_security
from nexusagent.tools.code_review.checks.style import check as _check_style
from nexusagent.tools.code_review.models import ReviewResult


def review_code(code: str, language: str = "python") -> str:
    """Analyze code for bugs, style issues, security vulnerabilities, and performance problems.

    Uses static analysis (pattern matching + AST for Python) to provide a structured
    review with severity levels. No LLM call required — works offline.

    Args:
        code: The source code to review
        language: Programming language (default: "python"). Affects AST analysis.

    Returns:
        Formatted review report with categorized issues and severity levels.
    """
    result = ReviewResult(lines_reviewed=len(code.splitlines()))

    if not code.strip():
        result.summary = "No code to review."
        return result.format_report()

    lines = code.splitlines()

    # Run all checks
    _check_security(code, lines, result)
    _check_bugs(code, lines, result)
    _check_style(code, lines, result)
    _check_performance(code, lines, result)

    # Python-specific AST analysis
    if language.lower() in ("python", "py"):
        _check_python_ast(code, result)

    return result.format_report()
