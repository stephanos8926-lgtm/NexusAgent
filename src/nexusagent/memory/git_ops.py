"""Git-backed memory operations — auto-commit after memory writes.

Provides :class:`MemoryGitOps` which wraps ``git init`` / ``git add`` / ``git commit``
with non-fatal error handling. All failures are logged but never propagate, so
memory operations succeed even when git is unavailable or misconfigured.
"""

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Rate limit: max 1 commit per second
_MIN_COMMIT_INTERVAL = 1.0


class MemoryGitOps:
    """Git operations for a memory workspace directory.

    All methods are non-fatal — they log errors and return gracefully.
    """

    def __init__(self, workspace_dir: str | Path):
        self.workspace = Path(workspace_dir)
        self._last_commit_ts: float = 0.0

    def init_repo(self) -> bool:
        """Initialize a git repo if ``.git`` doesn't already exist.

        Returns:
            True if repo was initialized or already exists, False on failure.
        """
        git_dir = self.workspace / ".git"
        if git_dir.exists():
            return True
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(self.workspace),
                capture_output=True,
                timeout=10,
            )
            logger.info("Initialized git repo in %s", self.workspace)
            return True
        except Exception as e:
            logger.warning("Failed to init git repo in %s: %s", self.workspace, e)
            return False

    def commit(self, message: str, files: list[str] | None = None) -> bool:
        """Stage files and commit. Rate-limited to 1 commit per second.

        Args:
            message: Commit message.
            files: List of relative paths to stage (e.g. ``["bank/foo.md"]``).
                If None, stages all changes (``git add -A``).

        Returns:
            True if commit succeeded, False on failure or rate-limit skip.
        """
        # Rate limiting
        now = time.monotonic()
        if now - self._last_commit_ts < _MIN_COMMIT_INTERVAL:
            logger.debug("Git commit rate-limited, skipping")
            return False

        try:
            # Stage files
            if files:
                subprocess.run(
                    ["git", "add", "--", *files],
                    cwd=str(self.workspace),
                    capture_output=True,
                    timeout=10,
                )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(self.workspace),
                    capture_output=True,
                    timeout=10,
                )

            # Commit (check if there's anything staged)
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(self.workspace),
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Nothing staged
                logger.debug("Nothing to commit")
                return False

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.workspace),
                capture_output=True,
                timeout=10,
            )
            self._last_commit_ts = time.monotonic()
            logger.info("Git commit: %s", message)
            return True
        except Exception as e:
            logger.warning("Git commit failed: %s", e)
            return False

    def log(self, limit: int = 10) -> list[dict[str, str]]:
        """Return recent commits.

        Args:
            limit: Maximum number of commits to return.

        Returns:
            List of dicts with ``hash``, ``message``, ``date`` keys.
        """
        try:
            result = subprocess.run(
                [
                    "git", "log", f"--max-count={limit}",
                    "--format=%H|%s|%ai",
                ],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return []
            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "date": parts[2],
                    })
            return commits
        except Exception as e:
            logger.warning("Git log failed: %s", e)
            return []
