"""
Code review tool for NexusAgent.

Provides static analysis and heuristic-based code review without requiring
an LLM call. Uses pattern matching to detect common bugs, security issues,
style problems, and anti-patterns across multiple languages.
"""

import ast
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
    SEVERITY_INFO: "ℹ️",
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
        """Add a new issue to the review result.

        Args:
            severity: One of SEVERITY_CRITICAL, SEVERITY_HIGH, etc.
            category: Issue category (e.g. "security", "bug", "style").
            message: Human-readable description of the issue.
            line: Optional 1-based line number.
            suggestion: Optional suggestion text for fixing the issue.
        """
        self.issues.append(Issue(severity, category, message, line, suggestion))

    def sort_issues(self):
        """Sort issues by severity (critical first, info last)."""
        self.issues.sort(key=lambda i: _SEVERITY_ORDER.get(i.severity, 99))

    def format_report(self) -> str:
        """Generate the full formatted review report.

        Groups issues by category, appends a severity summary,
        and returns the complete report string.

        Returns:
            Full markdown-style review report.
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

        lines.append(f"\n## Summary")
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


# ─── Security Checks ────────────────────────────────────────────────────

def _check_security(code: str, lines: list[str], result: ReviewResult):
    """Check for common security issues."""

    # Dangerous functions
    dangerous_patterns = [
        (r"\beval\s*\(", SEVERITY_CRITICAL, "eval() executes arbitrary code",
         "Use ast.literal_eval() for safe evaluation of literals"),
        (r"\bexec\s*\(", SEVERITY_CRITICAL, "exec() executes arbitrary code",
         "Avoid exec(); use safer alternatives"),
        (r"\bpickle\.loads?\s*\(", SEVERITY_HIGH, "pickle.load/loads can execute arbitrary code on deserialization",
         "Use json or a safe serialization format for untrusted data"),
        (r"\byaml\.load\s*\(", SEVERITY_HIGH, "yaml.load without SafeLoader can execute arbitrary code",
         "Use yaml.safe_load() instead"),
        (r"\bos\.system\s*\(", SEVERITY_HIGH, "os.system() is vulnerable to shell injection",
         "Use subprocess.run() with a list of arguments instead"),
        (r"\bsubprocess\..*shell\s*=\s*True", SEVERITY_HIGH, "subprocess with shell=True is vulnerable to injection",
         "Use shell=False (default) with a list of arguments"),
        (r"\.format\s*\(.*\)", SEVERITY_LOW, "str.format() with user input can leak information",
         "Use f-strings or parameterized approaches"),
        (r"%\s*\w", SEVERITY_LOW, "Old-style % formatting with user input can be unsafe",
         "Use f-strings or .format() with care"),
        (r"\binput\s*\(", SEVERITY_INFO, "input() in Python 2 is equivalent to eval(raw_input())",
         "Ensure you're using Python 3 where input() returns a string"),
        (r"\bhashlib\.md5\b", SEVERITY_LOW, "MD5 is cryptographically broken",
         "Use hashlib.sha256() for security-sensitive hashing"),
        (r"\bhashlib\.sha1\b", SEVERITY_LOW, "SHA-1 is cryptographically weak",
         "Use hashlib.sha256() for security-sensitive hashing"),
        (r"password\s*=\s*['\"]", SEVERITY_CRITICAL, "Hardcoded password detected",
         "Use environment variables or a secrets manager"),
        (r"secret\s*=\s*['\"]", SEVERITY_HIGH, "Hardcoded secret detected",
         "Use environment variables or a secrets manager"),
        (r"api_key\s*=\s*['\"]", SEVERITY_HIGH, "Hardcoded API key detected",
         "Use environment variables or a secrets manager"),
        (r"token\s*=\s*['\"]", SEVERITY_HIGH, "Hardcoded token detected",
         "Use environment variables or a secrets manager"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, severity, message, suggestion in dangerous_patterns:
            if re.search(pattern, line):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                result.add(severity, "security", message, i, suggestion)

    # SQL injection patterns
    for i, line in enumerate(lines, 1):
        if re.search(r"execute\s*\(\s*['\"].*%s", line) or re.search(r"execute\s*\(\s*f['\"]", line):
            result.add(SEVERITY_CRITICAL, "security",
                       "Possible SQL injection via string formatting in query", i,
                       "Use parameterized queries with ? or %s placeholders")

    # Weak crypto / SSL
    for i, line in enumerate(lines, 1):
        if re.search(r"ssl\._create_unverified_context", line):
            result.add(SEVERITY_HIGH, "security",
                       "Disabling SSL certificate verification", i,
                       "Use proper certificate validation")


# ─── Bug Checks ─────────────────────────────────────────────────────────

def _check_bugs(code: str, lines: list[str], result: ReviewResult):
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


# ─── Style Checks ───────────────────────────────────────────────────────

def _check_style(code: str, lines: list[str], result: ReviewResult):
    """Check for style issues."""

    # Lines too long
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            result.add(SEVERITY_LOW, "style",
                       f"Line too long ({len(line)} chars, recommend ≤120)", i,
                       "Break the line into multiple lines")
        elif len(line) > 99:
            result.add(SEVERITY_INFO, "style",
                       f"Line is {len(line)} chars (PEP 8 recommends ≤79, pragmatic limit ≤99)", i,
                       "Consider breaking the line")

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
                    if '"""' in next_line or "'''" in next_line or next_line.startswith("def ") or next_line.startswith("class "):
                        # Has docstring or next definition
                        break
                    elif next_line.startswith("pass") or next_line.startswith("..."):
                        result.add(SEVERITY_LOW, "style",
                                   "Function/class has only pass/ellipsis — needs implementation", i)
                        break
                    elif not (next_line.startswith("def ") or next_line.startswith("class ")):
                        # No docstring found
                        if j == i or (j == i + 1 and not lines[i].strip()):
                            result.add(SEVERITY_INFO, "style",
                                       "Public function/class missing docstring", i,
                                       "Add a docstring describing the purpose and parameters")
                        break


# ─── Performance Checks ─────────────────────────────────────────────────

def _check_performance(code: str, lines: list[str], result: ReviewResult):
    """Check for common performance issues."""

    # String concatenation in loops
    for i, line in enumerate(lines, 1):
        if re.search(r"for\s+.*:", line):
            # Simple heuristic: check if next few lines have += with strings
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


# ─── Python AST Checks ──────────────────────────────────────────────────

def _check_python_ast(code: str, result: ReviewResult):
    """Use Python AST for deeper analysis (Python code only)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        result.add(SEVERITY_CRITICAL, "bug",
                   f"Syntax error: {e.msg}", e.lineno,
                   "Fix the syntax error before further review")
        return

    for node in ast.walk(tree):
        # Check for unused imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if name not in code.split("import", 1)[-1]:
                    pass  # Can't easily detect unused imports without full analysis

        # Check for bare except in AST
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
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


# ─── Main Review Function ───────────────────────────────────────────────

def review_code(code: str, language: str = "python") -> str:
    """
    Analyze code for bugs, style issues, security vulnerabilities, and performance problems.

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
