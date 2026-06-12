"""Update internal imports after src/ reorganization.

Maps old flat module paths to new subpackage paths.
Only touches 'from nexusagent.X import' and 'import nexusagent.X' patterns.
"""
import re
from pathlib import Path

ROOT = Path("/home/sysop/Workspaces/NexusAgent")

# old_stem -> new dotted path (relative to nexusagent package)
RENAME = {
    "agent":        "core.agent",
    "session":     "core.session",
    "orchestration": "core.orchestration",
    "subagent":    "core.subagent",
    "worker":      "core.worker",
    "graph":       "core.graph",
    "compaction":  "memory.compaction",
    "memory":      "memory.memory",
    "memory_files": "memory.memory_files",
    "memory_index": "memory.memory_index",
    "llm":         "llm.llm",
    "models":      "llm.models",
    "config":      "infrastructure.config",
    "db":          "infrastructure.db",
    "bus":         "infrastructure.bus",
    "auth":        "infrastructure.auth",
    "api_auth":    "infrastructure.api_auth",
    "telemetry":   "infrastructure.telemetry",
    "utils":       "infrastructure.utils",
    "prompt_loader": "infrastructure.prompt_loader",
    "server":      "server.server",
    "sdk":         "server.sdk",
    "cli":         "interfaces.cli",
    "tui":         "interfaces.tui",
    "web_ui":      "interfaces.web_ui",
}

# Build regex: match "from nexusagent.OLD_STEM" or "import nexusagent.OLD_STEM"
# but NOT when followed by "." (which would mean it's already a subpackage reference)
pattern = re.compile(
    r'(from\s+nexusagent\.)(' + '|'.join(RENAME.keys()) + r')(\s|$|[^\w.])'
)

def replace_import(m):
    old_stem = m.group(2)
    suffix = m.group(3)
    return f"{m.group(1)}{RENAME[old_stem]}{suffix}"

changed_files = 0
for py_file in sorted(ROOT.rglob("*.py")):
    if ".egg-info" in str(py_file) or "__pycache__" in str(py_file):
        continue
    text = py_file.read_text()
    new_text = pattern.sub(replace_import, text)
    if new_text != text:
        py_file.write_text(new_text)
        rel = py_file.relative_to(ROOT)
        changed_files += 1
        print(f"  {rel}")

print(f"\n{changed_files} files updated")
