"""Security pattern checks for code review."""

from __future__ import annotations

import re

from nexusagent.tools.code_review.models import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_LOW,
    ReviewResult,
)


def check(code: str, lines: list[str], result: ReviewResult):
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
