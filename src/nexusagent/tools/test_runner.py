"""Test runner tool for NexusAgent.

Auto-detects test framework from repository structure and runs tests
with structured output parsing.
"""

import subprocess
from pathlib import Path


def _detect_test_framework(workdir: str) -> str | None:
    """Detect which test framework is used in the project."""
    p = Path(workdir)

    # Check for pytest
    if (p / "pytest.ini").exists() or (p / "pyproject.toml").exists() or (p / "setup.cfg").exists():
        return "pytest"
    if (p / "tests").is_dir():
        # Check if tests use pytest conventions
        test_files = list((p / "tests").glob("test_*.py"))
        if test_files:
            return "pytest"

    # Check for jest
    if (p / "package.json").exists():
        package_json = p / "package.json"
        try:
            import json

            pkg = json.loads(package_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "jest" in deps or "vitest" in deps:
                return "jest" if "jest" in deps else "vitest"
        except Exception:
            pass  # Dependency detection is best-effort
    if (p / "pom.xml").exists():
        return "maven"
    if (p / "build.gradle").exists() or (p / "build.gradle.kts").exists():
        return "gradle"

    # Check for go test
    go_files = list(p.glob("*_test.go"))
    if go_files:
        return "go"

    # Check for cargo (Rust)
    if (p / "Cargo.toml").exists():
        return "cargo"

    return None


def run_tests(
    workdir: str = ".",
    test_path: str | None = None,
    framework: str | None = None,
    timeout: int = 300,
    verbose: bool = True,
) -> str:
    """Run tests with auto-detection and structured output.

    Args:
        workdir: Project root directory
        test_path: Specific test file or directory to run (None = auto-detect)
        framework: Force a specific framework (None = auto-detect)
        timeout: Maximum execution time in seconds
        verbose: If True, show full test output

    Returns:
        Structured test results:
        ```
        Framework: pytest
        Exit code: 0
        Summary: 15 passed, 0 failed, 2 skipped
        ---
        <full output>
        ```
    """
    p = Path(workdir).resolve()
    if not p.is_dir():
        return f"Error: Directory '{workdir}' does not exist"

    # Detect framework
    fw = framework or _detect_test_framework(str(p))
    if not fw:
        return (
            "Error: Could not detect test framework. "
            "Supported: pytest, jest, vitest, maven, gradle, go, cargo. "
            "Use framework parameter to force a specific one."
        )

    # Build command as list (shell=False prevents injection)
    import re as _re

    if fw == "pytest":
        cmd = ["pytest"]
        if verbose:
            cmd.append("-v")
        cmd.extend(["--tb=short", "-q"])
        if test_path:
            # Validate test_path to prevent path traversal
            if not _re.match(r"^[a-zA-Z0-9/._-]+$", test_path):
                return f"Error: Invalid test_path '{test_path}' — only alphanumeric, /, ., _, - allowed"
            cmd.append(test_path)
        else:
            cmd.append("tests/")

    elif fw == "jest":
        cmd = ["npx", "jest"]
        if verbose:
            cmd.append("--verbose")
        if test_path:
            if not _re.match(r"^[a-zA-Z0-9/._-]+$", test_path):
                return f"Error: Invalid test_path '{test_path}' — only alphanumeric, /, ., _, - allowed"
            cmd.append(test_path)
        cmd.append("--no-coverage")

    elif fw == "vitest":
        cmd = ["npx", "vitest", "run"]
        if test_path:
            if not _re.match(r"^[a-zA-Z0-9/._-]+$", test_path):
                return f"Error: Invalid test_path '{test_path}' — only alphanumeric, /, ., _, - allowed"
            cmd.append(test_path)

    elif fw == "maven":
        cmd = ["mvn", "test"]
        if test_path:
            cmd.extend(["-Dtest", test_path])

    elif fw == "gradle":
        cmd = ["./gradlew", "test"] if (p / "gradlew").exists() else ["gradle", "test"]
        if test_path:
            cmd.extend(["--tests", test_path])

    elif fw == "go":
        cmd = ["go", "test", test_path] if test_path else ["go", "test", "./..."]
        if verbose:
            cmd.append("-v")

    elif fw == "cargo":
        cmd = ["cargo", "test"]
        if test_path:
            cmd.append(test_path)

    else:
        return f"Error: Unsupported framework '{fw}'"

    # Run
    try:
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(p),
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        # Parse summary
        summary = _parse_test_summary(output, fw)

        return f"Framework: {fw}\nExit code: {result.returncode}\nSummary: {summary}\n---\n{output}"

    except subprocess.TimeoutExpired:
        return f"Error: Tests timed out after {timeout}s"
    except Exception as e:
        return f"Error running tests: {e}"


def _parse_test_summary(output: str, framework: str) -> str:
    """Parse test output to extract a summary line."""
    if framework == "pytest":
        # Look for "X passed, Y failed, Z skipped" pattern
        import re

        match = re.search(r"(\d+ passed(?:, \d+ failed)?(?:, \d+ skipped)?)", output)
        if match:
            return match.group(1)

    elif framework in ("jest", "vitest"):
        import re

        match = re.search(r"Tests:\s+(\d+ passed(?:, \d+ failed)?(?:, \d+ total)?)", output)
        if match:
            return match.group(1)

    elif framework == "go":
        import re

        match = re.search(r"(ok|FAIL)\s+", output)
        if match:
            return match.group(1)

    return "unknown (check full output)"


def run_single_test(
    test_path: str,
    workdir: str = ".",
    framework: str | None = None,
    timeout: int = 60,
) -> str:
    """Run a single test file or test case.

    Args:
        test_path: Path to test file (e.g., "tests/test_auth.py")
        workdir: Project root directory
        framework: Force a specific framework
        timeout: Maximum execution time in seconds

    Returns:
        Test results
    """
    return run_tests(workdir=workdir, test_path=test_path, framework=framework, timeout=timeout)
