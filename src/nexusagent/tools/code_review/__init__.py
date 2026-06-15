"""Code review tool for NexusAgent.

Provides static analysis and heuristic-based code review without requiring
an LLM call. Uses pattern matching to detect common bugs, security issues,
style problems, and anti-patterns across multiple languages.

Subpackage structure:
- models.py: Issue, ReviewResult data classes
- checks/security.py: security pattern checks
- checks/bugs.py: common bug pattern checks
- checks/style.py: style issue checks
- checks/performance.py: performance issue checks
- checks/ast_check.py: Python AST-based analysis
- review_code.py: main review_code() orchestrator
"""

from __future__ import annotations

# Models (safe to import — no circular deps)
from nexusagent.tools.code_review.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    SEVERITY_INFO,
    Issue,
    ReviewResult,
)

# Main function (imports checks internally to avoid circular deps)
from nexusagent.tools.code_review.review_code import review_code

__all__ = [
    "SEVERITY_CRITICAL",
    "SEVERITY_HIGH",
    "SEVERITY_MEDIUM",
    "SEVERITY_LOW",
    "SEVERITY_INFO",
    "Issue",
    "ReviewResult",
    "review_code",
]
