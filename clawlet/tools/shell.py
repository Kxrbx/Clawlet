"""
Shell tool for executing commands.
"""

import asyncio
import shutil
from typing import Optional
from pathlib import Path

from clawlet.tools.registry import BaseTool, ToolResult


class ShellTool(BaseTool):
    """
    Tool for executing shell commands.
    
    SECURITY: This tool is powerful and potentially dangerous.
    Use allowed_commands to restrict which commands can run.
    """
    
    # Default safe commands
    DEFAULT_ALLOWED = [
        "ls", "cat", "head", "tail", "echo", "pwd", "whoami",
        "date", "uname", "df", "du", "free", "uptime",
        "git", "python", "python3", "pip", "pip3",
        "npm", "node", "yarn",
    ]
    
    def __init__(
        self,
        workspace: Optional[Path] = None,
        allowed_commands: Optional[list[str]] = None,
        timeout: float = 30.0,
        allow_all: bool = False,
    ):
        """
        Initialize shell tool.
        
        Args:
            workspace: Working directory for commands
            allowed_commands: List of allowed commands (None = use defaults)
            timeout: Command timeout in seconds
            allow_all: If True, allow any command (DANGEROUS)
        """
        self.workspace = workspace or Path.cwd()
        self.allowed_commands = set(allowed_commands or self.DEFAULT_ALLOWED)
        self.timeout = timeout
        self.allow_all = allow_all
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return """Execute shell commands. 
        Use for file operations, git, running scripts, etc.
        Commands run in the workspace directory with a timeout."""
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout in seconds (default: 30)",
                },
            },
            "required": ["command"],
        }
    
    async def execute(self, command: str, timeout: Optional[float] = None, **kwargs) -> ToolResult:
        """
        Execute a shell command.
        
        Args:
            command: The command to run
            timeout: Optional timeout override
            
        Returns:
            ToolResult with stdout/stderr
        """
        # Security check
        if not self._is_allowed(command):
            return ToolResult(
                success=False,
                output="",
                error=f"Command not allowed. Allowed: {', '.join(sorted(self.allowed_commands))}"
            )
        
        timeout = timeout or self.timeout
        
        try:
            # Run command in workspace
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout}s"
                )
            
            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            
            # Combine output
            output_parts = []
            if stdout_text.strip():
                output_parts.append(stdout_text.strip())
            if stderr_text.strip():
                output_parts.append(f"[stderr]\n{stderr_text.strip()}")
            
            output = "\n".join(output_parts) if output_parts else "(no output)"
            
            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=None if process.returncode == 0 else f"Exit code: {process.returncode}",
                data={
                    "returncode": process.returncode,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                }
            )
            
        except FileNotFoundError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Command not found: {command.split()[0]}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Execution error: {str(e)}"
            )
    
    def _is_allowed(self, command: str) -> bool:
        """Check if command is allowed."""
        if self.allow_all:
            return True
        
        # Extract base command
        base_cmd = command.strip().split()[0] if command.strip() else ""
        
        # Check if it's in allowed list
        return base_cmd in self.allowed_commands
    
    def add_allowed(self, *commands: str) -> None:
        """Add commands to allowed list."""
        self.allowed_commands.update(commands)
    
    def remove_allowed(self, *commands: str) -> None:
        """Remove commands from allowed list."""
        self.allowed_commands.difference_update(commands)
