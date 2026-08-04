import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from nexusagent.core.events.base import EventType, SystemEvent
from nexusagent.infrastructure.config import load_config, settings
from nexusagent.infrastructure.utils.security import sanitize_secrets
from nexusagent.memory.hybrid_memory import HybridMemoryManager
from nexusagent.tools.shell import run_shell


def test_secrets_redaction_utility():
    """Verify that sanitize_secrets redacts standard regexes and active values."""
    # Test regex patterns
    assert sanitize_secrets("My key is AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R") == "My key is [REDACTED]"
    assert "[REDACTED]" in sanitize_secrets("My secret sk-1234567890abcdef1234567890abcdef")
    assert "password='[REDACTED]'" in sanitize_secrets("password='secret123'")
    assert "api_key='[REDACTED]'" in sanitize_secrets("api_key='sk-or-v1-my-key'")

    # Test active secrets exact replacement (using an environment variable)
    os.environ["GEMINI_API_KEY"] = "super-secret-active-gemini-key-123456"
    assert "super-secret-active-gemini-key-123456" not in sanitize_secrets("API key is super-secret-active-gemini-key-123456")
    assert "[REDACTED]" in sanitize_secrets("API key is super-secret-active-gemini-key-123456")
    del os.environ["GEMINI_API_KEY"]


@pytest.mark.asyncio
async def test_secrets_redaction_memory(tmp_path):
    """Verify that HybridMemoryManager.remember redacts secrets before writing."""
    # Initialize a memory manager in test tmp_path
    manager = HybridMemoryManager(workspace_dir=tmp_path)
    manager.initialize()

    # Pass in content containing a simulated key
    secret_content = "Remember this api_key='sk-1234567890abcdef1234567890abcdef' for my project."
    filepath_str = await manager.remember(content=secret_content, type="observation")

    # Assert that the written file on disk is redacted
    disk_content = Path(filepath_str).read_text()
    assert "sk-1234567890" not in disk_content
    assert "[REDACTED]" in disk_content

    # Clean up DB index connections
    await manager.close()


def test_secrets_redaction_events():
    """Verify that SystemEvent.to_dict() redacts secrets from payloads and tracing."""
    class TestEvent(SystemEvent):
        category = EventType.TASK

    # Event with secrets in payload and tracing
    event = TestEvent(
        source="test",
        type="task.test",
        payload={"command": "api_key='sk-1234567890abcdef1234567890abcdef'", "output": "success"},
        tracing={"trace_id": "sk-1234567890abcdef1234567890abcdef"}
    )

    data = event.to_dict()
    assert "sk-1234567890" not in str(data["payload"])
    assert "sk-1234567890" not in str(data["tracing"])
    assert "[REDACTED]" in str(data["payload"])
    assert "[REDACTED]" in str(data["tracing"])


def test_config_immutability(monkeypatch):
    """Verify that settings attributes are immutable (frozen)."""
    monkeypatch.setenv("NEXUS_TEST_MODE", "0")
    with pytest.raises(TypeError) as exc_info:
        settings.server.api_port = 9000
    assert "frozen" in str(exc_info.value).lower() or "immutable" in str(exc_info.value).lower()

    with pytest.raises(TypeError) as exc_info:
        settings.client.tui_theme = "light"
    assert "frozen" in str(exc_info.value).lower() or "immutable" in str(exc_info.value).lower()


def test_config_validators_port(tmp_path):
    """Verify that port constraints are enforced."""
    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("server:\n  api_port: 999999")  # Invalid port

    with pytest.raises(ValidationError) as exc_info:
        load_config(str(config_file))
    assert "less_than_equal" in str(exc_info.value).lower() or "api_port" in str(exc_info.value).lower()


def test_config_validators_tls(tmp_path):
    """Verify that TLS file mismatch is rejected."""
    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("server:\n  tls_enabled: true\n  tls_certfile: /path/to/cert.pem")  # Cert but no key

    with pytest.raises(ValidationError) as exc_info:
        load_config(str(config_file))
    assert "tls_certfile" in str(exc_info.value).lower() or "tls_keyfile" in str(exc_info.value).lower()


def test_config_validators_production(tmp_path, monkeypatch):
    """Verify production security policies are enforced under production env."""
    monkeypatch.setenv("NEXUS_ENV", "production")

    config_file = tmp_path / "nexusagent.yaml"
    # Lacks client API key in production environment
    config_file.write_text("client:\n  api_key: ''\nserver:\n  tls_enabled: false")

    with pytest.raises(ValidationError) as exc_info:
        load_config(str(config_file))
    assert "security error" in str(exc_info.value).lower()


def test_shell_sandbox_denials():
    """Verify that dangerous shell commands and sensitive paths are denied."""
    # Sudo/Su denial
    res = run_shell("sudo apt-get update")
    assert "[SANDBOX DENIAL]" in res
    assert "prohibited" in res.lower()

    # Chmod/Chown denial
    res = run_shell("chmod +x script.sh")
    assert "[SANDBOX DENIAL]" in res

    # Root-level rm denial
    res = run_shell("rm -rf /")
    assert "[SANDBOX DENIAL]" in res
    assert "prohibited" in res.lower()

    # Sensitive path accesses
    res = run_shell("cat /etc/passwd")
    assert "[SANDBOX DENIAL]" in res
    assert "access to sensitive path" in res.lower()

    res = run_shell("grep secret ~/.ssh/id_rsa")
    assert "[SANDBOX DENIAL]" in res
