"""Style checks for code review."""

from __future__ import annotations

import re

from nexusagent.tools.code_review.models import (
    SEVERITY_INFO,
    SEVERITY_LOW,
    ReviewResult,
)


def check(code: str, lines: list[str], result: ReviewResult):
    """Check for style issues."""

    # Lines too long
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            result.add(
                SEVERITY_LOW,
                "style",
                f"Line too long ({len(line)} chars, recommend ≤120)",
                i,
                "Break the line into multiple lines",
            )
        elif len(line) > 99:
            result.add(
                SEVERITY_INFO,
                "style",
                f"Line is {len(line)} chars (PEP 8 recommends ≤79, pragmatic limit ≤99)",
                i,
                "Consider breaking the line",
            )

    # Trailing whitespace
    for i, line in enumerate(lines, 1):
        if line != line.rstrip():
            result.add(SEVERITY_INFO, "style", "Trailing whitespace", i, "Remove trailing spaces")

    # Missing docstring for public functions/classes
    for i, line in enumerate(lines, 1):
        if re.match(r"^def\s+[a-z_]\w*\s*\(", line) or re.match(r"^class\s+[A-Z]\w*", line):
            # Check if next non-empty line has a docstring
            for j in range(i, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("#"):
                    if (
                        '"""' in next_line
                        or "'''" in next_line
                        or next_line.startswith("def ")
                        or next_line.startswith("class ")
                    ):
                        break
                    elif next_line.startswith("pass") or next_line.startswith("..."):
                        result.add(
                            SEVERITY_LOW,
                            "style",
                            "Function/class has only pass/ellipsis — needs implementation",
                            i,
                        )
                        break
                    elif not (next_line.startswith("def ") or next_line.startswith("class ")):
                        if j == i or (j == i + 1 and not lines[i].strip()):
                            result.add(
                                SEVERITY_INFO,
                                "style",
                                "Public function/class missing docstring",
                                i,
                                "Add a docstring describing the purpose and parameters",
                            )
                        break
