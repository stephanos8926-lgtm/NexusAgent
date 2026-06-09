# tests/test_cli_run.py
"""Tests for the 'nexus run' CLI command."""

from click.testing import CliRunner

from nexusagent.cli import main


def test_run_command_exists():
    """Verify that 'nexus run --help' exits successfully and mentions the task argument."""
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "task" in result.output.lower()
