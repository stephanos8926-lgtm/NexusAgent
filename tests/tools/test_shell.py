from nexusagent.tools.shell import run_shell


def test_shell_tool():
    result = run_shell("echo hello")
    assert result.strip() == "hello"
