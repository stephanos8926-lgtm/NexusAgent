import inspect

from nexusagent.infrastructure.config import load_config
from nexusagent.llm.llm import LLMProvider


def test_load_config_success(tmp_path, monkeypatch):
    # Clear any env vars that would override the test config
    monkeypatch.delenv("NEXUS_SERVER__DB_PATH", raising=False)
    monkeypatch.delenv("NEXUS_SERVER__NATS_URL", raising=False)

    # Mocking yaml file
    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("server:\n  nats_url: nats://test\n  db_path: test.db")

    from unittest.mock import patch

    with patch("nexusagent.infrastructure.config.get_nexus_home", return_value=tmp_path):
        config = load_config(str(config_file))
        assert config.server.nats_url == "nats://test"
        assert config.server.db_path.endswith("test.db")


def test_llm_timeout_default():
    sig = inspect.signature(LLMProvider.generate)
    assert 'timeout' in sig.parameters
    assert sig.parameters['timeout'].default == 120.0
