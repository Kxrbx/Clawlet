"""
Tests for shell tool security.
"""

import pytest
from pathlib import Path

from clawlet.tools.shell import ShellTool, DANGEROUS_PATTERNS
from clawlet.tools.registry import ToolResult


class TestShellToolSecurity:
    """Test shell tool security measures."""
    
    @pytest.fixture
    def shell_tool(self, tmp_path: Path) -> ShellTool:
        """Create a shell tool for testing."""
        return ShellTool(workspace=tmp_path)
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("malicious_command", [
        # Command chaining
        "ls; rm -rf /",
        "ls && rm -rf /",
        "ls || rm -rf /",
        "ls & rm -rf /",
        # Pipes to shells
        "ls | sh",
        "ls | bash",
        "cat file | sh",
        # Subshells
        "ls $(whoami)",
        "ls `whoami`",
        "echo $(cat /etc/passwd)",
        # Redirects to sensitive files
        "ls > /etc/passwd",
        "cat file > /dev/sda",
        # Dangerous commands
        "rm -rf /",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs /dev/sda",
        "chmod 777 /etc/passwd",
    ])
    async def test_blocks_malicious_commands(self, shell_tool: ShellTool, malicious_command: str):
        """Test that malicious commands are blocked."""
        result = await shell_tool.execute(malicious_command)
        
        assert result.success is False
        assert "not allowed" in result.error.lower() or "blocked" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_allows_safe_commands(self, shell_tool: ShellTool):
        """Test that safe commands are allowed."""
        result = await shell_tool.execute("echo hello")
        
        assert result.success is True
        assert "hello" in result.output
    
    @pytest.mark.asyncio
    async def test_blocks_unknown_commands(self, shell_tool: ShellTool):
        """Test that unknown commands are blocked."""
        result = await shell_tool.execute("hacker_command arg1 arg2")
        
        assert result.success is False
        assert "not allowed" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_timeout_works(self, shell_tool: ShellTool):
        """Test that command timeout works."""
        # This command would hang forever without timeout
        result = await shell_tool.execute("sleep 100", timeout=0.5)
        
        assert result.success is False
        assert "timeout" in result.error.lower()
    
    def test_dangerous_patterns_comprehensive(self):
        """Test that dangerous patterns cover common attacks."""
        # Ensure we have patterns for common attacks
        pattern_strings = "".join(DANGEROUS_PATTERNS)
        
        assert ";" in pattern_strings, "Missing semicolon pattern"
        assert "&&" in pattern_strings, "Missing && pattern"
        assert "||" in pattern_strings, "Missing || pattern"
        assert "\\$\\(" in "".join(DANGEROUS_PATTERNS), "Missing subshell pattern"
        assert "`" in pattern_strings, "Missing backtick pattern"
        assert "| sh" in pattern_strings.lower() or "\\|\\s*sh" in pattern_strings, "Missing pipe to shell"
    
    @pytest.mark.asyncio
    async def test_workspace_isolation(self, shell_tool: ShellTool, tmp_path: Path):
        """Test that commands run in the workspace directory."""
        # Create a test file in workspace
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        result = await shell_tool.execute("ls")
        
        assert result.success is True
        assert "test.txt" in result.output


class TestShellToolConfiguration:
    """Test shell tool configuration options."""
    
    @pytest.mark.asyncio
    async def test_custom_allowed_commands(self, tmp_path: Path):
        """Test custom allowed commands list."""
        tool = ShellTool(
            workspace=tmp_path,
            allowed_commands=["echo", "ls"],
        )
        
        # Allowed command
        result = await tool.execute("echo test")
        assert result.success is True
        
        # Normally allowed but not in custom list
        result = await tool.execute("pwd")
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_add_remove_commands(self, tmp_path: Path):
        """Test adding and removing commands."""
        tool = ShellTool(workspace=tmp_path)
        
        # pwd should be allowed by default
        result = await tool.execute("pwd")
        assert result.success is True
        
        # Remove pwd
        tool.remove_allowed("pwd")
        result = await tool.execute("pwd")
        assert result.success is False
        
        # Add it back
        tool.add_allowed("pwd")
        result = await tool.execute("pwd")
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_get_allowed_commands(self, tmp_path: Path):
        """Test getting allowed commands list."""
        tool = ShellTool(
            workspace=tmp_path,
            allowed_commands=["echo", "ls", "pwd"],
        )
        
        allowed = tool.get_allowed()
        
        assert "echo" in allowed
        assert "ls" in allowed
        assert "pwd" in allowed
        assert len(allowed) == 3
