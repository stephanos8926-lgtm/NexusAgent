# Changelog

## v0.1.0 (2026-07-09)

### Added
- Policy-aware tool discovery system with three levels (permissive, restricted, strict)
- Role-based tool manifests (minimal, reader, writer, coder, tester, reviewer, debugger, researcher, full)
- Auto-unlock on first call in permissive mode
- Fuzzy tool name matching with "Did you mean...?" suggestions
- Parameter validation with auto-correction hints
- `edit_file` tool: surgical line-range edit with old_text validation
- `git_*` tools: full git operations
- `test_runner` tool: auto-detect pytest/jest/maven/gradle/go/cargo
- `search_code`, `find_symbol`, `find_references`: ripgrep-based code search
- Thread-local policy context for concurrent parent/sub-agents
- mkdocs-material documentation site with auto-generated API docs
- Makefile with targets: all, test, lint, format, typecheck, security, docs

### Changed
- `read_file`: added line-range support (offset + limit params)
- `list_directory`: added glob pattern filtering and default excludes
- `run_shell`: added timeout, workdir, env params
- `write_file`: enforce read-before-write safety for existing files
- All pre-existing lint errors fixed (0 remaining)
