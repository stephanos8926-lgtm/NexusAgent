# Enhanced NexusAgent Design Specification

## 1. Tool Enhancements & Additions
- **Shell Tool:** Refactored to return a structured response: `{"stdout": str, "stderr": str, "exit_code": int}`.
- **`list_directory`:** Implemented with nested tree structure output, `recursive` flag, and `max_depth`.
- **Batch Operations:** `read_multiple_files` and `write_multiple_files` added.
- **Safety Layer:** Added a "Read-Before-Write" session state check. All write operations must verify the path has been read in the current session.
- **Surgical Edits:** Added `apply_patch` using unified diff format to minimize token usage and improve precision.

## 2. Configuration & Customization
- **System Prompt:** Extracted to `config/system_prompt.txt` for easy customization.
- **Runtime Config:** `config/nexusagent.yaml` created for both server (NATS url, db path) and client (TUI colors, NATS url).

## 3. Client (TUI Interface)
- **TUI Library:** Moving from `argparse` to `textual` for an iterative, interactive development interface inspired by `gemini-cli`.
- **Features:** Real-time log streaming, iterative task submission, interactive error correction feedback loop (when tool fails, agent prompts user for guidance via TUI).

## 4. Error Correction & Resilience
- **Self-Correction:** Agents will be instructed via the system prompt to utilize structured tool errors (`stderr` and exit codes) to debug and retry actions automatically.
- **User Intervention:** When an agent reaches a terminal error, it will use a NATS topic `task.error` to push the error state, which the TUI will display, prompting the user for guidance to resume or restart.
