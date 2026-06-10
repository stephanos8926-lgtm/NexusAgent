# Feature Parity Research — Capabilities Perspective

> Research date: 2026-06-10
> Products analyzed: Claude Code, Gemini CLI, Qwen Code CLI, OpenCode, Aider
> NexusAgent current state: 176/193 tests passing, 36 source files, 40 test files

---

## 1. Tool Comparison

| Tool Category | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **File Read** | ✅ Read (line ranges) | ✅ Read | ✅ Read | ✅ Read | ✅ Read | ✅ read_file |
| **File Write** | ✅ Write, Edit | ✅ Write | ✅ Write | ✅ Write | ✅ Edit | ✅ write_file, edit_file |
| **File Search** | ✅ Grep, Glob | ✅ Grep, Glob | ✅ Grep, Glob | ✅ Grep, Glob | ✅ Grep | ✅ search_code, find_symbol, find_references |
| **Shell** | ✅ Bash | ✅ Shell | ✅ Shell | ✅ Bash | ✅ Shell | ✅ run_shell, run_shell_streaming |
| **Git** | ✅ (via Bash) | ✅ (via Bash) | ✅ (via Bash) | ✅ (via Bash) | ✅ Auto-commit | ✅ 9 git tools |
| **Web Search** | ✅ WebSearch | ✅ Google Search | ✅ Web Search | ✅ websearch (Exa) | ✅ Web Fetch | ✅ search_web (Exa→Tavily) |
| **Web Fetch** | ✅ WebFetch | ✅ Fetch | ✅ Fetch | ✅ webfetch | ✅ Web Pages | ✅ fetch_url |
| **LSP** | ✅ Code Intelligence plugins | ❌ | ❌ | ✅ LSP (experimental) | ❌ | ❌ |
| **Todo/Plan** | ✅ TodoWrite/Read | ✅ Todos | ✅ Todos | ✅ todowrite | ❌ | ❌ |
| **Subagent** | ✅ Agent tool (named + forked) | ✅ Subagents | ✅ SubAgents | ✅ Multi-session | ❌ | ✅ spawn_subagent |
| **MCP** | ✅ Full MCP support | ✅ MCP servers | ✅ MCP servers | ✅ MCP servers | ❌ | ❌ |
| **Skills** | ✅ Bundled + custom | ✅ Agent Skills | ✅ Skills | ✅ Custom tools | ❌ | ❌ |
| **Memory** | ✅ CLAUDE.md hierarchy | ✅ GEMINI.md + auto-extract | ✅ QWEN.md | ✅ AGENTS.md | ❌ | ✅ Hybrid memory (files + FTS5 + vectors) |
| **Ask User** | ✅ AskUserQuestion | ✅ | ✅ | ✅ ask_user | ❌ | ✅ ask_user |
| **Images** | ✅ Image input | ✅ | ✅ | ✅ Drag-and-drop | ✅ Images | ❌ |
| **Voice** | ❌ | ❌ | ❌ | ❌ | ✅ Voice-to-code | ❌ |
| **Repo Map** | ❌ | ❌ | ❌ | ❌ | ✅ Tree-sitter + PageRank | ❌ |
| **Undo/Redo** | ✅ /undo, /redo | ✅ Rewind | ✅ | ✅ /undo, /redo | ✅ git revert | ❌ |
| **Apply Patch** | ✅ | ✅ | ✅ | ✅ apply_patch | ❌ | ✅ apply_patch |
| **Multi-file Edit** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ write_multiple_files |
| **Test Runner** | ✅ (via Bash) | ✅ (via Bash) | ✅ (via Bash) | ✅ (via Bash) | ✅ Auto-lint/test | ✅ run_tests, run_single_test |

---

## 2. Agent Modes

| Mode | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **Default (interactive)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Plan mode** | ✅ (Shift+Tab) | ✅ Plan Mode | ✅ | ✅ Plan mode | ❌ | ❌ |
| **Auto-accept edits** | ✅ | ✅ Unified Auto | ✅ --yolo | ✅ permission system | ✅ | ❌ |
| **YOLO mode** | ✅ Auto mode | ✅ | ✅ --yolo | ✅ | ✅ | ❌ |
| **Headless/Scriptable** | ✅ --print | ✅ --output-format json | ✅ --output-format json | ✅ | ✅ --yes | ❌ |
| **Background agent** | ✅ /background | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Batch mode** | ✅ /batch (parallel worktrees) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Role-based** | ✅ Subagent types | ✅ Agent Skills | ✅ | ✅ | ❌ | ✅ Role manifests (full/restricted) |

---

## 3. Context Management

| Feature | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **Context window** | 200K | 1M (Gemini) | 1M+ | Model-dependent | Model-dependent | Model-dependent |
| **Compaction** | ✅ 7-layer defense | ✅ Auto-compact | ✅ | ✅ | ❌ | ✅ 4-layer graduated |
| **Memory files** | ✅ CLAUDE.md hierarchy | ✅ GEMINI.md | ✅ QWEN.md | ✅ AGENTS.md | ❌ | ✅ NEXUS.md hierarchy |
| **@file injection** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ @file chaining |
| **Auto memory extract** | ❌ | ✅ From transcripts | ✅ | ❌ | ❌ | ✅ Hybrid memory |
| **Token counting** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Session resume** | ✅ UUID chain | ✅ Checkpointing | ✅ --resume | ✅ | ❌ | ✅ SessionManager |
| **Session fork** | ✅ Fork mode | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 4. Multi-Agent Features

| Feature | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **Subagents** | ✅ Named + forked | ✅ Built-in types | ✅ | ✅ Multi-session | ❌ | ✅ spawn_subagent |
| **Parallel agents** | ✅ /batch + /tasks | ✅ Remote agents | ✅ | ✅ Multi-session | ❌ | ✅ WorkerPool |
| **Agent teams** | ✅ (experimental) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Remote agents** | ❌ | ✅ Remote subagents | ✅ Daemon mode | ❌ | ❌ | ❌ |
| **Agent SDK** | ✅ | ✅ | ✅ TS/Python/Java | ✅ | ❌ | ✅ Python SDK |
| **ACP protocol** | ❌ | ❌ | ✅ (experimental) | ❌ | ❌ | ❌ |

---

## 5. Slash Commands

| Command | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **/help** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **/clear** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **/compact** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **/model** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **/undo** | ✅ | ✅ Rewind | ✅ | ✅ | ❌ | ❌ |
| **/redo** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **/init** | ✅ CLAUDE.md | ✅ GEMINI.md | ✅ QWEN.md | ✅ AGENTS.md | ❌ | ✅ NEXUS.md |
| **/permissions** | ✅ | ✅ Policy engine | ✅ | ✅ | ❌ | ❌ |
| **/agents** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **/tasks** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **/batch** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **/background** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **/skills** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **/connect** | ❌ | ❌ | ❌ | ✅ OAuth | ❌ | ❌ |
| **/theme** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ (5 themes) |
| **/tokens** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **/version** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **/copy** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ (stub) |
| **/sessions** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ (stub) |
| **/status** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **/interrupt** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **/expand** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **/collapse** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 6. Configuration

| Feature | Claude Code | Gemini CLI | Qwen Code | OpenCode | Aider | NexusAgent |
|---|---|---|---|---|---|---|
| **Settings file** | ✅ settings.json | ✅ settings.json | ✅ settings.json | ✅ config.yaml | ✅ .aider.conf.yml | ✅ config.yaml |
| **Env variables** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Project config** | ✅ CLAUDE.md | ✅ GEMINI.md | ✅ QWEN.md | ✅ AGENTS.md | ❌ | ✅ NEXUS.md |
| **Global config** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Model providers** | ✅ Multi | ✅ Multi | ✅ Multi (5+) | ✅ 75+ | ✅ Multi | ✅ Multi |
| **Permission rules** | ✅ Granular | ✅ Policy engine | ✅ | ✅ Per-tool | ❌ | ✅ Role-based |
| **Themes** | ✅ 69 semantic tokens | ✅ | ✅ | ✅ | ❌ | ✅ 5 themes |
| **Keybindings** | ✅ Customizable | ✅ | ✅ | ✅ | ❌ | ✅ Fixed set |
| **Hooks** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Plugins** | ✅ (beta) | ✅ Extensions | ❌ | ❌ | ❌ | ❌ |

---

## 7. Tier Analysis for NexusAgent

### 🔴 CRITICAL (Must have — blocking issues)

1. **LSP Integration** — Claude Code and OpenCode both have LSP. NexusAgent has zero code intelligence (no go-to-definition, no hover, no references via LSP). This is a massive gap for code understanding.
2. **Todo/Plan tool** — Every competitor has a todowrite/todos tool for multi-step task tracking. NexusAgent has no equivalent. The agent cannot track its own progress on complex tasks.
3. **Undo/Redo** — Claude Code, Qwen Code, and OpenCode all support undo/redo. NexusAgent has no way to revert changes.
4. **YOLO mode** — All competitors have a way to auto-approve all actions. NexusAgent's approval system has no bypass mode.
5. **Headless/Scriptable mode** — Gemini CLI and Qwen Code both support `--output-format json` for scripting. NexusAgent has no headless mode.
6. **MCP client** — Claude Code, Gemini CLI, Qwen Code, and OpenCode all support MCP servers. NexusAgent has NO MCP client capability. This is the #1 extensibility gap.
7. **Image input** — Claude Code, Qwen Code, OpenCode, and Aider all support image input. NexusAgent cannot process images.
8. **Session resume** — Qwen Code has `--resume`, Gemini CLI has checkpointing. NexusAgent's session resume is basic.

### 🟡 MANDATORY (Needed for daily workflow)

9. **Skills system** — Claude Code and Gemini CLI have bundled skills (code-review, debug, etc.). NexusAgent has no skill system.
10. **Hooks** — Claude Code, Gemini CLI, and Qwen Code support hooks (pre/post command execution). NexusAgent has none.
11. **Repo map** — Aider's tree-sitter repo map is a killer feature for large codebases. NexusAgent has no equivalent.
12. **Auto-commit** — Aider auto-commits with AI attribution. NexusAgent requires manual git operations.
13. **Lint/test on edit** — Aider auto-lints and tests after every edit. NexusAgent has test runner tools but no auto-execution.
14. **Permission rules** — Claude Code's granular permission system (per-tool, per-path, per-command) is far more sophisticated than NexusAgent's role-based system.
15. **Background agent** — Claude Code's `/background` and Qwen Code's daemon mode allow long-running tasks. NexusAgent has no background execution.
16. **Batch mode** — Claude Code's `/batch` for parallel worktree-based changes is a powerful feature for large refactors.
17. **Token counting** — All competitors show token usage. NexusAgent has no token counter in the TUI.
18. **Model routing** — Gemini CLI's auto-routing between Flash and Pro is a great UX pattern.

### 🟢 NICE TO HAVE (Polish)

19. **Voice input** — Aider's voice-to-code is unique and useful.
20. **Desktop app** — OpenCode has a desktop app. Terminal-only is fine for now.
21. **Share links** — OpenCode's session sharing is nice for collaboration.
22. **Plugin marketplace** — Claude Code's plugin ecosystem is powerful.
23. **ACP protocol** — Qwen Code's Agent Communication Protocol is forward-looking.
24. **Agent teams** — Claude Code's experimental agent teams for complex multi-agent workflows.
25. **Followup suggestions** — Qwen Code's ghost text predictions.
26. **OAuth/login** — OpenCode's `/connect` for GitHub Copilot, ChatGPT.
27. **Custom keybindings** — All competitors allow remapping keys.
28. **Semantic theme tokens** — Claude Code's 69 semantic tokens vs NexusAgent's 5 hardcoded themes.

---

## 8. Key Takeaways

### What NexusAgent does BETTER:
- **Memory system** — Hybrid files + FTS5 + vector search is more sophisticated than any competitor
- **Git tools** — 9 dedicated git tools vs competitors' "use bash for git"
- **Policy system** — Permissive/restricted/strict with auto-unlock is unique
- **NEXUS.md** — @file chaining with circular detection is more advanced than CLAUDE.md
- **Compaction** — 4-layer graduated compaction is on par with Claude Code's 7-layer

### What NexusAgent is MISSING (in priority order):
1. **MCP client** — This is the biggest gap. MCP is the industry standard for tool extensibility.
2. **LSP integration** — Code intelligence is essential for a coding agent.
3. **Todo/Plan tool** — Multi-step task tracking is table stakes.
4. **Headless mode** — Scripting/CI support is essential for automation.
5. **Skills system** — Bundled skills (code-review, debug) are expected.
6. **YOLO mode** — Auto-approve is a daily-use feature.
7. **Undo/Redo** — Safety net for AI changes.
8. **Image input** — Visual context is increasingly important.
9. **Hooks** — Automation at key workflow points.
10. **Repo map** — Large codebase understanding.

---

## 9. Recommended Implementation Priority

### Sprint 1 (CRITICAL — Week 1):
1. MCP client integration
2. Todo/Plan tool
3. YOLO mode
4. Headless mode (--output-format json)

### Sprint 2 (MANDATORY — Week 2):
5. LSP integration (via MCP or direct)
6. Skills system (bundled: code-review, debug, security-review)
7. Undo/Redo
8. Image input support

### Sprint 3 (POLISH — Week 3):
9. Hooks system
10. Repo map (tree-sitter based)
11. Auto-commit with AI attribution
12. Auto-lint/test on edit
