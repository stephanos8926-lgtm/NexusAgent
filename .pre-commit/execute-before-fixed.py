#!/usr/bin/env python3
"""
Pre-commit hook to enforce "execute before claiming fixed" policy.
Checks commit messages for "fix" or "fixed" keywords and verifies that tests
were actually modified or added in the commit.
"""
import subprocess
import sys
import re

def get_commit_message():
    """Get the commit message from git."""
    result = subprocess.run(
        ["git", "log", "-1", "--pretty=%B"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

def get_changed_files():
    """Get list of files changed in the commit."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
        capture_output=True,
        text=True
    )
    return result.stdout.strip().split()

def has_fix_keyword(message):
    """Check if commit message contains fix/fixed keywords."""
    fix_patterns = [
        r'\bfix\b', r'\bfixed\b', r'\bfixes\b', r'\bfixing\b',
        r'\bresolve\b', r'\bresolved\b', r'\bresolves\b',
        r'\bclose\b', r'\bclosed\b', r'\bcloses\b',
        r'\baddress\b', r'\baddressed\b', r'\baddresses\b',
    ]
    message_lower = message.lower()
    return any(re.search(pattern, message_lower) for pattern in fix_patterns)

def has_test_changes(changed_files):
    """Check if any test files were modified."""
    test_patterns = [
        r'test_.*\.py$',
        r'.*_test\.py$',
        r'.*/tests/.*\.py$',
        r'conftest\.py$',
    ]
    for f in changed_files:
        for pattern in test_patterns:
            if re.search(pattern, f):
                return True
    return False

def main():
    message = get_commit_message()
    changed_files = get_changed_files()
    
    if not has_fix_keyword(message):
        # No fix keyword, allow commit
        return 0
    
    # Check if tests were modified
    if not has_test_changes(changed_files):
        print("ERROR: Commit message contains 'fix/fixed' but no test files were modified.")
        print("Policy: Commits claiming a fix must include test changes.")
        print("Changed files:", ", ".join(changed_files) if changed_files else "none")
        print("Commit message:", message[:200])
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())