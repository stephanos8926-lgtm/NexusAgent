# Jules — File Change Verification (Critical)

**Problem:** Jules PR #13 created a commit with a message but ZERO file changes. This wasted a full cycle because the cloud sandbox built the code locally but never pushed the files to the branch.

**Root cause:** The git push step inside Jules's VM likely failed silently. The commit was created but `git push origin HEAD:branch-name` disconnected the actual file changes.

**Prevention:**
1. Always run `git status` and `git diff --cached --stat` BEFORE `git commit`
2. Verify files are staged: `git diff --cached --name-only | head -20`
3. After commit, verify: `git diff-tree --no-commit-id -r HEAD --name-only | wc -l` should be > 0
4. After push, verify branch has content: `git diff origin/BRANCH_NAME^..origin/BRANCH_NAME --stat`

**Recovery if this happens again:**
- The Jules session `4093038977148740812` still has the code in its VM
- Send `send_message(session_id, 'Git push: git push origin HEAD:branch-name')` to trigger a re-push
- If that fails, re-dispatch with `auto_pr=True` so Jules uses the automatic PR flow instead of manual push
