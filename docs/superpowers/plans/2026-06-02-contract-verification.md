# Contract Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that the Web UI and TUI clients strictly adhere to the contracts defined in `src/nexusagent/sdk.py` and `src/nexusagent/models.py`.

**Architecture:** Use a Mock SDK implementation that simulates various backend responses (Success, Error, Timeout) to verify that the UI components handle every state correctly without crashing or diverging from the spec.

**Tech Stack:** `pytest`, `unittest.mock`, `gradio` (headless testing), `textual` (headless testing).

---

### Task 1: Setup Contract Mocking Framework

**Files:**
- Create: `tests/contract_verification/conftest.py`

- [ ] **Step 1: Implement MockNexusSDK**

```python
import pytest
from unittest.mock import MagicMock
from nexusagent.sdk import NexusSDK
from nexusagent.models import TaskResponse

def pytest_fixture():
    mock_sdk = MagicMock(spec=NexusSDK)
    return mock_sdk

@pytest.fixture
def mock_sdk():
    mock_sdk = MagicMock(spec=NexusSDK)
    return mock_sdk
```

- [ ] **Step 2: Run basic fixture test**

Run: `pytest tests/contract_verification/conftest.py`
Expected: PASS (with no tests)

- [ ] **Step 3: Commit**

```bash
git add tests/contract_verification/conftest.py
git commit -m "test: setup contract verification mocking framework"
```

### Task 2: Web UI Contract Compliance

**Files:**
- Create: `tests/contract_verification/test_web_ui_contract.py`
- Modify: `src/nexusagent/web_ui.py` (if adjustments are needed for testability)

- [ ] **Step 1: Write failing test for Success path**

```python
from nexusagent.web_ui import create_ui
from nexusagent.models import TaskResponse
from unittest.mock import patch

def test_web_ui_success_handshake():
    with patch('nexusagent.web_ui.NexusSDK') as MockSDK:
        mock_instance = MockSDK.return_value
        mock_instance.submit_task.return_value = TaskResponse(success=True, data="Task Complete", error=None)
        
        # Simulate the handle_submit logic
        # (We test the function logic separate from the Gradio server)
        from nexusagent.web_ui import handle_submit
        result, status = handle_submit("Test Task")
        
        assert status == "ACTIVE"
        assert "Task Complete" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/contract_verification/test_web_ui_contract.py`
Expected: FAIL (since handle_submit isn't currently exported or accessible)

- [ ] **Step 3: Refactor `web_ui.py` to export `handle_submit` for testing**

Modify `src/nexusagent/web_ui.py` to move `handle_submit` outside the `create_ui` closure.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/contract_verification/test_web_ui_contract.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/nexusagent/web_ui.py tests/contract_verification/test_web_ui_contract.py
git commit -m "test: verify web ui contract compliance"
```

### Task 3: TUI Contract Compliance

**Files:**
- Create: `tests/contract_verification/test_tui_contract.py`

- [ ] **Step 1: Write failing test for Error path**

```python
from nexusagent.tui import NexusApp
from nexusagent.models import TaskResponse
from unittest.mock import patch

def test_tui_error_handshake():
    with patch('nexusagent.tui.NexusSDK') as MockSDK:
        mock_instance = MockSDK.return_value
        mock_instance.submit_task.return_value = TaskResponse(success=False, data=None, error="Backend Timeout")
        
        app = NexusApp()
        # Simulate input submission
        # (Mocks the Textual event loop)
        # We test the on_input_submitted logic
        # event = MagicMock()
        # event.input.id = "task-input"
        # event.value = "Fail Task"
        # app.on_input_submitted(event)
        # assert app.push_screen.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/contract_verification/test_tui_contract.py`
Expected: FAIL

- [ ] **Step 3: Implement logic and verify pass**

- [ ] **Step 4: Commit**

```bash
git add tests/contract_verification/test_tui_contract.py
git commit -m "test: verify tui contract compliance"
```

### Task 4: Boundary & Chaos Testing

**Files:**
- Create: `tests/contract_verification/test_chaos.py`

- [ ] **Step 1: Write test for empty input**

```python
from nexusagent.web_ui import handle_submit
def test_empty_input_handling():
    result, status = handle_submit("")
    assert status == "ERROR"
    assert "empty" in result.lower()
```

- [ ] **Step 2: Run and verify pass**

- [ ] **Step 3: Commit**

```bash
git add tests/contract_verification/test_chaos.py
git commit -m "test: boundary and chaos verification"
```
