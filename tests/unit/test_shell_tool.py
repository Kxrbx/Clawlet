from __future__ import annotations

from pathlib import Path

import pytest

from clawlet.tools.shell import ShellTool


@pytest.mark.unit
def test_shell_tool_whitelist_and_dangerous_patterns(tmp_path: Path):
    tool = ShellTool(workspace=tmp_path)

    assert tool._validate_command("git status") == (True, "")
    assert tool._validate_command("curl https://example.com")[0] is False
    assert tool._validate_command("git status && git diff")[0] is False
    assert tool._validate_command('python -c "print(1) if True else print(2)"')[0] is False


@pytest.mark.unit
def test_shell_tool_extracts_segment_commands_and_allows_dangerous_bypass(tmp_path: Path):
    safe = ShellTool(workspace=tmp_path)
    dangerous = ShellTool(workspace=tmp_path, allow_dangerous=True, allowed_commands=["git", "python"])

    assert safe._extract_segment_commands(["git", "status", "&&", "python", "-V"]) == ["git", "python"]
    assert dangerous._validate_command("git status && python -V") == (True, "")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shell_tool_times_out(tmp_path: Path):
    tool = ShellTool(
        workspace=tmp_path,
        timeout=0.01,
        allowed_commands=["python"],
        allow_dangerous=True,
        use_rust_core=False,
    )

    result = await tool.execute('python -c "(__import__(\"time\").sleep(1.0))"')

    assert result.success is False
    assert "timed out" in (result.error or "")
