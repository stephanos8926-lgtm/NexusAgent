# Specification: LLXPRT /review Skill

This document defines the architecture and behavior of the `/review` skill, ported from `qwen-code`.

## 1. Objective
Provide a professional-grade, multi-stage code review pipeline that combines deterministic analysis (linters/typecheckers) with parallel multi-agent LLM reasoning and a verification pass.

## 2. Pipeline Architecture

The `/review` command follows a 11-step pipeline:

### Step 1: Scope Determination
- **Inputs**: `[pr-number|file-path] [--comment]`
- **Logic**:
  - Resolve PR number $\rightarrow$ URL $\rightarrow$ Owner/Repo.
  - Detect if same-repo or cross-repo.
  - If same-repo: trigger `fetch-pr` $\rightarrow$ creates worktree at `.llxprt/tmp/review-pr-<n>`.
  - If cross-repo: trigger "Lightweight Mode" (diff-only).
  - Handle local uncommitted changes via `git diff`.

### Step 2: Project Rules Loading
- **Source**: `.llxprt/review-rules.md`, `.github/copilot-instructions.md`, `AGENTS.md` (Code Review section).
- **Output**: A combined rule set injected into review agents.

### Step 3: Deterministic Analysis
- **Tooling**: Runs language-specific checks:
  - **TS/JS**: `tsc --noEmit`, `eslint`
  - **Python**: `ruff check`
  - **Rust**: `cargo clippy`
  - **Go**: `go vet`, `golangci-lint`
- **Logic**: Filter results to *only* modified files in the diff.
- **Output**: JSON list of confirmed findings.

### Step 4: Multi-Agent Parallel Review
Launch 9 agents concurrently (one `task` per agent):
1. **Correctness**: Logic, edge cases, boundaries.
2. **Security**: Injections, XSS, secrets, auth bypass.
3. **Code Quality**: Style, duplication, over-engineering.
4. **Performance**: Bottlenecks, leaks, algorithms.
5. **Test Coverage**: Missing tests for new paths.
6. **Undirected Audit (3 Personas)**:
   - *Attacker*: Malicious input/state.
   - *Oncall*: Production failure modes/debuggability.
   - *Maintainer*: Future landmines/tech debt.
7. **Build & Test**: Verifies compilation and test success.

### Step 5: Deduplication & Verification
- **Merge**: Group findings by file:line.
- **Verify**: A single verification agent reads the code $\rightarrow$ confirms/rejects each finding.
- **Aggregation**: Group repeating patterns across the codebase.

### Step 6: Iterative Reverse Audit
- Run 1-3 rounds of a "Gap-Finding" agent that sees all prior findings and looks for what was missed.

### Step 7: Reporting
- **Terminal**: Summary $\rightarrow$ Findings $\rightarrow$ Verdict $\rightarrow$ Tips.
- **PR Comments**: Verdict $\rightarrow$ Inline comments via GitHub "Create Review" API.

### Step 8: Autofix
- Offer to apply fixes using the `edit` tool.
- Commit and push fixes from the worktree to the PR branch.

### Step 9: Submit PR Review
- Use `gh api .../reviews` to post the unified review in one call.

### Step 10: Persistence
- Save report to `.llxprt/reviews/<timestamp>-target.md`.
- Update incremental cache in `.llxprt/review-cache/pr-<n>.json`.

### Step 11: Cleanup
- Remove worktrees, refs, and temp files.

## 3. Tool Mappings

| Qwen-Code Command | LLXPRT Implementation |
| :--- | :--- |
| `qwen review fetch-pr` | `.llxprt/scripts/review_fetch_pr.sh` |
| `qwen review deterministic` | `.llxprt/scripts/review_deterministic.sh` |
| `qwen review pr-context` | `.llxprt/scripts/review_pr_context.sh` |
| `qwen review presubmit` | `.llxprt/scripts/review_presubmit.sh` |
| `qwen review cleanup` | `.llxprt/scripts/review_cleanup.sh` |

## 4. Success Criteria
- Correctly handles fork PRs without contaminating local branch.
- Identifies a known critical bug via deterministic analysis.
- Identifies a subtle logic flaw via the "Oncall" persona.
- Posts high-confidence findings to GitHub without duplicating noise.
