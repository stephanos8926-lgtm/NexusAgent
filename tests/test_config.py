import os
from nexusagent.config import load_config


def test_load_config_success(tmp_path, monkeypatch):
    # Clear any env vars that would override the test config
    monkeypatch.delenv("NEXUS_SERVER__DB_PATH", raising=False)
    monkeypatch.delenv("NEXUS_SERVER__NATS_URL", raising=False)

    # Mocking yaml file
    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("server:\n  nats_url: nats://test\n  db_path: test.db")

    from unittest.mock import patch
    with patch("nexusagent.config.get_project_root", return_value=tmp_path):
        config = load_config("nexusagent.yaml")
        assert config.server.nats_url == "nats://test"
        assert config.server.db_path.endswith("test.db")
