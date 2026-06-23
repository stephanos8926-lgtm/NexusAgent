"""Python AST-based checks for code review."""

from __future__ import annotations

import ast

from nexusagent.tools.code_review.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    ReviewResult,
)


def check(code: str, result: ReviewResult):
    """Use Python AST for deeper analysis (Python code only)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.add(SEVERITY_CRITICAL, "bug",
                   f"Syntax error: {e.msg}", e.lineno,
                   "Fix the syntax error before further review")
        return

    for node in ast.walk(tree):
        # Check for bare except in AST
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            result.add(SEVERITY_MEDIUM, "bug",
                       "Bare except clause (AST)", node.lineno,
                       "Use 'except Exception:' or a specific type")

        # Check for return in __init__
        if isinstance(node, ast.FunctionDef) and node.name == "__init__":
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    result.add(SEVERITY_HIGH, "bug",
                               "__init__ should not return a value", child.lineno,
                               "Remove the return value; __init__ should only set attributes")
