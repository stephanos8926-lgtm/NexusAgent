"""Bug pattern checks for code review."""

from __future__ import annotations

import re

from nexusagent.tools.code_review.models import (
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    SEVERITY_INFO,
    ReviewResult,
)


def check(code: str, lines: list[str], result: ReviewResult):
    """Check for common bugs and logic errors."""

    # Mutable default arguments (Python)
    for i, line in enumerate(lines, 1):
        if re.search(r"def\s+\w+\s*\(.*=\s*\[\s*\]", line):
            result.add(SEVERITY_HIGH, "bug",
                       "Mutable default argument (list) — shared across calls", i,
                       "Use None as default and initialize inside the function")
        if re.search(r"def\s+\w+\s*\(.*=\s*\{\s*\}", line):
            result.add(SEVERITY_HIGH, "bug",
                       "Mutable default argument (dict) — shared across calls", i,
                       "Use None as default and initialize inside the function")

    # Bare except
    for i, line in enumerate(lines, 1):
        if re.search(r"except\s*:", line):
            result.add(SEVERITY_MEDIUM, "bug",
                       "Bare except clause catches all exceptions including KeyboardInterrupt", i,
                       "Use 'except Exception:' or a more specific exception type")

    # == None / != None
    for i, line in enumerate(lines, 1):
        if re.search(r"==\s*None", line) or re.search(r"!=\s*None", line):
            result.add(SEVERITY_LOW, "bug",
                       "Use 'is None' or 'is not None' instead of == or !=", i,
                       "Replace with 'is None' / 'is not None'")

    # Variable shadowing builtins
    builtin_names = {"list", "dict", "set", "str", "int", "float", "bool", "type", "id", "input", "max", "min", "sum", "map", "filter", "all", "any"}
    for i, line in enumerate(lines, 1):
        for name in builtin_names:
            if re.search(rf"\b{name}\s*=\s*", line) and not line.strip().startswith("#"):
                result.add(SEVERITY_MEDIUM, "bug",
                           f"Variable '{name}' shadows a Python builtin", i,
                           f"Rename to avoid shadowing the builtin '{name}'")
                break

    # Unused variable _ pattern (info)
    for i, line in enumerate(lines, 1):
        if re.search(r"except\s+\w+\s+as\s+_\s*:", line):
            result.add(SEVERITY_INFO, "bug",
                       "Exception caught but assigned to _ (unused)", i,
                       "Consider logging or handling the exception")

    # TODO/FIXME without context
    for i, line in enumerate(lines, 1):
        if re.search(r"#\s*TODO\b", line, re.IGNORECASE) and len(line.strip()) < 15:
            result.add(SEVERITY_INFO, "maintainability",
                       "TODO comment without actionable detail", i,
                       "Add a specific action item or ticket reference to the TODO")
