# Enhanced NexusAgent Design Specification

## 1. Tool Enhancements & Additions
- **Shell Tool:** Refactored to return a structured response: `{"stdout": str, "stderr": str, "exit_code": int}`.
- **`list_directory`:** Implemented with nested tree structure output, `recursive` flag, and `max_depth`.
- **Batch Operations:** `read_multiple_files` and `write_multiple_files` added.
- **Safety Layer:** Added a "Read-Before-Write" session state check. All write operations must verify the path has been read in the current session.
- **Surgical Edits:** Added `apply_patch` using unified diff format to minimize token usage and improve precision.

## 2. Autonomous Research & Self-Healing
- **Loop Detection:** If a node is re-entered more than **4 times** consecutively ("Loop Threshold"), trigger a **"Research Branch."**
- **Autonomous Research:** Agent uses `Context7` (local docs) and `ExaSearch` (web search) to debug.
- **Correction:** After researching, the agent attempts the task up to **4 additional times** autonomously before halting or alerting.

## 3. Configuration & Customization
- **System Prompt:** Extracted to `config/system_prompt.txt`.
- **Runtime Config:** `config/nexusagent.yaml` for both server (NATS url, db path) and client (TUI colors, NATS url).
- **Configurable Parameters:** `loop_threshold: 4`, `post_research_retries: 4`, `notification_channels: [telegram_token, webhook_url]`.

## 4. Client (TUI Interface)
- **TUI Library:** `textual` for an iterative, interactive development interface.
- **Features:** Real-time log streaming, iterative task submission, interactive error correction feedback loop.

## 5. Error Correction & Resilience
- **Self-Correction:** Agents utilize structured tool errors (`stderr`, `exit_code`) to debug and retry actions.
- **User Intervention:** When terminal errors occur:
    - **TUI Mode:** Halts and prompts user for guidance.
    - **Headless Mode:** Pushes error state to `task.error` topic, sends notification via configured channels, and halts.
