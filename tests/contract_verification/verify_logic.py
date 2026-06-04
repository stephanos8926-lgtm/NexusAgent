import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class TaskSchema:
    id: str
    description: str

@dataclass
class TaskResponse:
    success: bool
    data: Optional[str] = None
    error: Optional[str] = None

class MockSDK:
    def submit_task(self, task):
        # This is where we simulate the contract
        if "fail" in task.description.lower():
            return TaskResponse(success=False, error="Simulated Failure")
        return TaskResponse(success=True, data="Simulated Success")

def handle_submit_logic(text, sdk):
    if not text:
        return "Error: Task definition empty", "ERROR"
    task_id = str(uuid.uuid4())[:8]
    task = TaskSchema(id=task_id, description=text)
    result = sdk.submit_task(task)
    if result.success:
        return f"[{task_id}] {result.data}", "ACTIVE"
    else:
        return f"Critical Failure: {result.error}", "ERROR"

# --- TESTS ---
def test_success():
    sdk = MockSDK()
    res, stat = handle_submit_logic("Do something", sdk)
    assert stat == "ACTIVE"
    assert "Simulated Success" in res
    print("✓ Success Path Verified")

def test_failure():
    sdk = MockSDK()
    res, stat = handle_submit_logic("Please fail", sdk)
    assert stat == "ERROR"
    assert "Simulated Failure" in res
    print("✓ Error Path Verified")

def test_empty():
    sdk = MockSDK()
    res, stat = handle_submit_logic("", sdk)
    assert stat == "ERROR"
    assert "empty" in res
    print("✓ Empty Input Verified")

if __name__ == "__main__":
    test_success()
    test_failure()
    test_empty()
    print("\nALL CONTRACT LOGIC VERIFIED")
