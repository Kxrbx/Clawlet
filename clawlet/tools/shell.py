"""
Shell tool for executing commands.

SECURITY: This tool uses multiple layers of protection:
1. Command whitelist - only allowed base commands
2. Pattern blocking - detects dangerous operators
3. Safe execution - uses exec instead of shell
"""

import asyncio
import shlex
import re
import shutil
from typing import Optional
from pathlib import Path

from loguru import logger

from clawlet.tools.registry import BaseTool, ToolResult


# Dangerous patterns that should never be allowed
DANGEROUS_PATTERNS = [
    # Command chaining
    r';',           # command1; command2
    r'&&',          # command1 && command2
    r'\|\|',        # command1 || command2
    # Pipes to shells
    r'\|\s*sh\b',   # | sh
    r'\|\s*bash\b', # | bash
    r'\|\s*zsh\b',  # | zsh
    r'\|\s*fish\b', # | fish
    # Subshells
    r'\$\(',        # $(command)
    r'`',           # `command`
    # Redirects to sensitive files
    r'>\s*/etc/',   # > /etc/*
    r'>\s*/dev/sd', # > /dev/sda
    r'>\s*/dev/hd', # > /dev/hda
    # Backgrounding
    r'&\s*$',       # command &
    # Dangerous commands even if in whitelist
    r'\brm\s+-rf\s+/',      # rm -rf /
    r'\bdd\s+if=',          # dd if=
    r'\bmkfs\b',            # mkfs
    r'\bfdisk\b',           # fdisk
    r'\bchmod\s+777',       # chmod 777
    r'\bchown\s+.*:',       # chown user:
]


class ShellTool(BaseTool):
    """
    Tool for executing shell commands.
    
    SECURITY: Multiple protection layers:
    - Whitelist of allowed base commands
    - Block dangerous patterns (pipes, redirects, subshells)
    - Use exec() instead of shell() for safe execution
    """
    
    # Default safe commands (read-only or safe operations)
    DEFAULT_ALLOWED = [
        # File listing/reading
        "ls", "cat", "head", "tail", "less", "more", "file",
        "wc", "find", "tree", "stat",
        # System info (read-only)
        "pwd", "whoami", "date", "uname", "hostname",
        "df", "du", "free", "uptime", "top", "htop", "ps",
        "env", "printenv", "which", "type",
        # Development tools
        "git", "python", "python3", "pip", "pip3",
        "npm", "node", "yarn", "pnpm",
        "cargo", "rustc", "go",
        # Text processing (safe)
        "echo", "printf", "grep", "sed", "awk", "cut",
        "sort", "uniq", "diff", "patch",
        # Archive tools (extraction only)
        "tar", "unzip", "gunzip", "bunzip2",
    ]
    
    def __init__(
        self,
        workspace: Optional[Path] = None,
        allowed_commands: Optional[list[str]] = None,
        timeout: float = 30.0,
        allow_dangerous: bool = False,
    ):
        """
        Initialize shell tool.
        
        Args:
            workspace: Working directory for commands
            allowed_commands: List of allowed commands (None = use defaults)
            timeout: Command timeout in seconds
            allow_dangerous: If True, skip pattern checks (still needs whitelist)
        """
        self.workspace = workspace or Path.cwd()
        self.allowed_commands = set(allowed_commands or self.DEFAULT_ALLOWED)
        self.timeout = timeout
        self.allow_dangerous = allow_dangerous
        
        logger.info(f"ShellTool initialized with {len(self.allowed_commands)} allowed commands")
    
    @property
    def name(self) -> str:
        return "shell"
    
    @property
    def description(self) -> str:
        return """Execute shell commands safely.
        
Use for file operations, git, running scripts, etc.
Commands run in the workspace directory with a timeout.

Security: Only whitelisted commands are allowed.
Dangerous patterns (pipes, redirects, subshells) are blocked."""
    
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
        Execute a shell command safely.
        
        Args:
            command: The command to run
            timeout: Optional timeout override
            
        Returns:
            ToolResult with stdout/stderr
        """
        # Security check 1: Validate command
        is_allowed, error_msg = self._validate_command(command)
        if not is_allowed:
            logger.warning(f"Blocked command: {error_msg}")
            return ToolResult(
                success=False,
                output="",
                error=error_msg
            )
        
        timeout = timeout or self.timeout
        
        try:
            # Parse command safely
            args = shlex.split(command)
            base_cmd = args[0]
            
            # Find the full path to the command
            cmd_path = shutil.which(base_cmd)
            if cmd_path is None:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command not found: {base_cmd}"
                )
            
            # Run command WITHOUT shell (safe execution)
            process = await asyncio.create_subprocess_exec(
                cmd_path,
                *args[1:],
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
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass  # Process may already be terminated
                logger.warning(f"Command timed out: {command}")
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout}s"
                )
            finally:
                if process.returncode is None:
                    try:
                        process.kill()
                        await process.wait()
                    except Exception:
                        pass
            
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
            
            logger.info(f"Command executed: {base_cmd} (exit code: {process.returncode})")
            
            return ToolResult(
                success=process.returncode == 0,
                output=output,
                error=None if process.returncode == 0 else f"Exit code: {process.returncode}",
                data={
                    "returncode": process.returncode,
                    "command": command,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                }
            )
            
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ToolResult(
                success=False,
                output="",
                error=f"Execution error: {str(e)}"
            )
    
    def _validate_command(self, command: str) -> tuple[bool, str]:
        """
        Validate command for security.
        
        Returns:
            (is_allowed, error_message)
        """
        if not command or not command.strip():
            return False, "Empty command"
        
        command = command.strip()
        
        # Security check 2: Block dangerous patterns
        if not self.allow_dangerous:
            for pattern in DANGEROUS_PATTERNS:
                if re.search(pattern, command):
                    return False, f"Blocked pattern detected in command"
        
        # Security check 3: Parse and validate base command
        try:
            args = shlex.split(command)
        except ValueError as e:
            return False, f"Invalid command syntax: {e}"
        
        if not args:
            return False, "Empty command"
        
        base_cmd = args[0]
        
        # Check if base command is in whitelist
        if base_cmd not in self.allowed_commands:
            allowed_list = ", ".join(sorted(self.allowed_commands)[:10])
            return False, f"Command '{base_cmd}' not allowed. Allowed: {allowed_list}..."
        
        return True, ""
    
    def add_allowed(self, *commands: str) -> None:
        """Add commands to allowed list."""
        self.allowed_commands.update(commands)
        logger.info(f"Added commands to whitelist: {commands}")
    
    def remove_allowed(self, *commands: str) -> None:
        """Remove commands from allowed list."""
        self.allowed_commands.difference_update(commands)
        logger.info(f"Removed commands from whitelist: {commands}")
    
    def get_allowed(self) -> list[str]:
        """Get list of allowed commands."""
        return sorted(self.allowed_commands)
