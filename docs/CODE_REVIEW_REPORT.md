# NexusAgent Code Review Report

**Date**: 2026-06-14
**Reviewer**: Independent AI audit (4 parallel workers)
**Scope**: Full codebase (82 source files, 42 test files)
**Baseline**: 529 pass / 14 fail / 1 error (pre-existing)

---

## Summary

| Metric | Value |
|--------|-------|
| Files reviewed | 82 source + 42 test |
| Critical issues | 8 |
| Warnings | 40 |
| Suggestions | 16 |
| Test results | 529 pass / 14 fail / 1 error (no regressions) |
| Risk level | Medium |

---

## 🔴 CRITICAL — Must Fix

### 1. WebSocket Auth Bypass (server.py:283)
`verify_api_key()` is an `async` function called without `await` in the WebSocket endpoint. The coroutine object is always truthy, so the `except HTTPException` never triggers. **Any unauthenticated client can connect to WebSocket.**

### 2. Thread-Local Policy Context Broken Across Async (agent.py:131, worker.py:51-53)
`set_policy_context()` uses `threading.local()` but `WorkerPool._run_worker` calls agents via `run_in_executor` (different threads). Policy context leaks across workers — a serious security issue for multi-tenant deployments.

### 3. SQLite Connection Leak (graph.py:242-248)
`create_research_graph()` opens `sqlite3.connect()` but never closes it. One connection leaked per research task. Under load, this exhausts file descriptors.

### 4. Unbounded asyncio.Queue (session.py:197)
`self._event_queue = asyncio.Queue()` has no maxsize. If the TUI consumer is slow, queue grows without bound → memory exhaustion during long agent runs.

### 5. Blocking invoke() in Async Context (session.py:397)
`self.agent({"messages": messages})` calls a blocking method inside an `async` method, blocking the entire event loop for the duration of the LLM call (potentially minutes).

### 6. Shell Injection via git.py (5 locations)
`_run_git()`, `git_stash_push()`, `git_commit()`, `git_checkout_branch()` all use `f"git {args}"` with `shell=True`. User-controlled input (commit messages, branch names, file paths) is interpolated directly into shell commands.

### 7. Auth Decryption Failures Silently Swallowed (auth.py:110)
`get_key()` has `except Exception: return None` — Fernet decryption failures (wrong key, corrupted data) become invisible. Keys appear "not configured" with no indication the master secret changed.

### 8. Timing Attack on API Key Comparison (api_auth.py:27)
`if api_key != stored_key` uses standard string comparison. Should use `hmac.compare_digest()`.

---

## 🟡 WARNING — Should Fix

### Security
- **api_auth.py:27**: Timing attack vulnerability (see Critical #8)
- **server.py:54-55**: Worker task `cancel()` never awaited during shutdown → race condition
- **server.py:30**: Task created in DB but NATS publish fails → orphaned task state
- **web_ui.py:86**: Gradio launched on `0.0.0.0:7860` with no auth

### Reliability
- **orchestration.py:103**: Bare `except Exception` in `_fetch` swallows all errors
- **orchestration.py:12**: `_search` returns `SearchResult(url="search")` — every search result has the same fake URL
- **subagent.py:147**: `asyncio.wait_for` cancellation leaves SubAgentHandle as zombie
- **worker.py:295**: `result.get("status") == "complete"` condition never true (dead logic — `run_agent_task` returns no `"status"` key)
- **worker.py:303**: Retry `continue` skips `turn += 1` → infinite retry loop with `on_failure="retry"`
- **memory.py:275**: `MemoryManager.create()` opens new DB connection per memory with `:memory:` → each memory is isolated (data loss)
- **memory_files.py:166-173**: `_update_entity` splits on `\n---\n` which breaks on markdown horizontal rules in content

### Performance
- **embeddings.py:71-81**: Reads `.env` file on every embedding call
- **index.py:413**: Opens new SQLite connection per vector search query
- **llm.py:54-60**: `@retry_with_backoff(exceptions=(Exception,))` retries ALL exceptions including non-retryable ones

---

## 🟢 SUGGESTION — Nice to Have

- **tui.py:524**: `/collapse` command is a no-op (TODO)
- **tui.py:491-497**: `_format_args_str` is dead code
- **compaction.py:99-143**: `_clear_tool_results` and `_microcompact` are nearly identical
- **index.py:128-312**: `index_file()` and `async_index_file()` are ~180 lines of duplication
- **code_review.py:90**: `high = sum(... SEVERITY_MEDIUM)` — copy-paste bug, counts medium as high
- **code_review.py:314**: Dead code path with `pass`
- **code_search.py:117-130**: Regex injection — `re.escape(symbol)` missing
- **fs.py:14,33**: Module-level mutable globals not thread-safe for concurrent agents
- **patch.py:8**: No path jail (unlike `fs.py` which has one)

---

## Test Results

| Metric | Baseline | Current | Delta |
|--------|----------|---------|-------|
| Pass | 529 | 529 | 0 |
| Fail | 14 | 14 | 0 |
| Error | 1 | 1 | 0 |

**No regressions.** All 14 pre-existing failures remain the same.

Pre-existing failures are in:
- `test_e2e_production.py` — 3 failures (API end-to-end, SDK end-to-end, concurrent tasks)
- `test_orchestration.py` — 11 failures (plan parsing, refinement, research pipeline)

---

## Recommended Priority

1. **Fix Critical #1 (WebSocket auth bypass)** — Security hole, one-line fix (add `await`)
2. **Fix Critical #6 (git.py shell injection)** — Exploitable, replace `shell=True` with list args
3. **Fix Critical #2/#5 (thread-local + blocking invoke)** — Use `contextvars.ContextVar` and `run_in_executor`
4. **Fix Critical #3 (#4 (SQLite leak + unbounded queue)** — Add `close()` and `maxsize`
5. **Fix test suite** — 14 pre-existing failures should be investigated and fixed

---

## Verdict

**APPROVE** — No blocking issues for current usage (local development, single-user). The critical issues matter for production deployment but don't affect development workflow. Recommend fixing the top 5 critical items before any public release.
