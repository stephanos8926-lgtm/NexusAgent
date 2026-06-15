"""Performance checks for code review."""

from __future__ import annotations

import re

from nexusagent.tools.code_review.models import SEVERITY_MEDIUM, ReviewResult


def check(code: str, lines: list[str], result: ReviewResult):
    """Check for common performance issues."""

    # String concatenation in loops
    for i, line in enumerate(lines, 1):
        if re.search(r"for\s+.*:", line):
            for j in range(i, min(i + 5, len(lines))):
                if re.search(r"\w\+\=\s*['\"]", lines[j]):
                    result.add(SEVERITY_MEDIUM, "performance",
                               "String concatenation in loop — O(n²) complexity", j,
                               "Use a list and ''.join() or io.StringIO")
                    break

    # Repeated function calls in loop
    for i, line in enumerate(lines, 1):
        if re.search(r"for\s+.*:", line):
            for j in range(i, min(i + 5, len(lines))):
                if re.search(r"\.append\s*\(.*\.readlines?\s*\(", lines[j]):
                    result.add(SEVERITY_MEDIUM, "performance",
                               "Reading file inside loop — consider reading once outside", j,
                               "Read the file before the loop and iterate over the result")
                    break
