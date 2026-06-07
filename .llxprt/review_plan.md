# Implementation Plan: LLXPRT /review Skill

This plan outlines the steps to port the `/review` skill and its helper infrastructure from `qwen-code` to `llxprt`.

## Phase 1: Infrastructure Setup (The Helpers)
The "Helpers" are the core deterministic power of the skill. They will be implemented as Python scripts in `/home/sysop/.llxprt/scripts` to ensure stability, portability, and powerful JSON processing.

### 1.1. Basic Directory Setup
- Ensure `/home/sysop/.llxprt/scripts/` exists (executables).
- Ensure `/home/sysop/.llxprt/tmp/` exists (ephemeral files).
- Ensure `/home/sysop/.llxprt/review-cache/` exists (incremental data).

### 1.2. `review_fetch_pr.py`
- Implement stale worktree removal (`git worktree remove`).
- Implement unique local ref fetching (`git fetch ... pull/n/head:ref`).
- Implement `gh pr view` metadata extraction via `subprocess`.
- Implement worktree creation (`git worktree add`).
- **Test**: Successfully create a worktree for a public PR.

### 1.3. `review_deterministic.py`
- Implement the "Tool Registry" in Python:
  - Detect `tsconfig.json` $\rightarrow$ run `tsc` and `eslint`.
  - Detect `pyproject.toml` $\rightarrow$ run `ruff`.
  - Detect `Cargo.toml` $\rightarrow$ run `cargo clippy`.
  - Detect `go.mod` $\rightarrow$ run `go vet`.
- Implement the "Filter" logic: only output findings for files listed in a provided `changed-files.json`.
- **Test**: Trigger a type error in a test file and verify it's caught.

### 1.4. `review_pr_context.py`
- Implement paginated `gh api` calls for PR comments and reviews using `requests` or `subprocess`.
- Implement thread reconstruction logic (root + replies).
- Generate the Markdown context file.
- **Test**: Generate a context file for a PR with multiple reply chains.

### 1.5. `review_presubmit.py`
- Implement self-PR check.
- Implement CI status classification.
- Implement the "Overlap" check (finding existing Qwen comments at same line).
- **Test**: Verify "Approve" is downgraded to "Comment" for self-PRs.

### 1.6. `review_cleanup.py`
- Implement idempotent cleanup of worktrees and refs.
- **Test**: Ensure no residual `.llxprt/tmp` files remain.

## Phase 2: Skill Orchestration (The Prompt)
The intelligence layer.

### 2.1. Porting the `SKILL.md`
- Adapt the Qwen `SKILL.md` to reference `python3 /home/sysop/.llxprt/scripts/review_...py` instead of `qwen review ...`.
- Integrate with `llxprt`'s existing `task` and `run_shell_command` tools.
- Ensure the 9-agent parallel launch is explicitly instructed in the prompt.

### 2.2. Skill Registration
- Install the refined prompt into the `llxprt` skill system.

## Phase 3: Validation & Hardening
Final quality check.

### 3.1. End-to-End Test Case
- Create a "Buggy PR" mock repo.
- Run `/review 123` $\rightarrow$ verify all 11 steps complete.
- **Test**: Verify the final verdict is correctly influenced by deterministic analysis and LLM findings.

### 3.2. Edge-Case Hardening
- Handle `gh` authentication failures.
- **Test**: Verify the "Lightweight Mode" triggers for cross-repo PRs.
- **Test**: Verify "Incremental Review" skips analysis if SHA matches.

## Phase 4: Handoff
- Final documentation of how to use the skill.
- User usage guide.
