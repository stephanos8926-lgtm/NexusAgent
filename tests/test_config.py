from nexusagent.config import load_config


def test_load_config_success(tmp_path):
    # Mocking yaml file
    config_file = tmp_path / "nexusagent.yaml"
    config_file.write_text("server:\n  nats_url: nats://test\n  db_path: test.db")
    
    # We need to monkeypatch get_project_root to return tmp_path/config
    # Or just mock load_config
    from unittest.mock import patch
    with patch("nexusagent.config.get_project_root", return_value=tmp_path):
        config = load_config("nexusagent.yaml")
        assert config.nats_url == "nats://test"
        assert config.db_path == "test.db"