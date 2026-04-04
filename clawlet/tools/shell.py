"""
Shell tool for executing commands.

SECURITY: This tool uses multiple layers of protection:
1. Command whitelist - only allowed base commands
2. Pattern blocking - detects dangerous operators
3. Safe execution - uses exec instead of shell
"""

import asyncio
import os
import shlex
import re
import shutil
from typing import Optional
from pathlib import Path

from loguru import logger

from clawlet.runtime.rust_bridge import execute_command_argv as rust_execute_command_argv
from clawlet.tools.registry import BaseTool, ToolResult


# Regex checks operate on the raw command string before tokenization. They are
# used for shell constructs or destructive invocations that should be rejected
# outright in safe mode, even if later token parsing would succeed.
RAW_DANGEROUS_PATTERNS = [
    # Command chaining / shell flow control
    (r';', 'command chaining with ";"'),
    (r'&&', 'command chaining with "&&"'),
    (r'\|\|', 'command chaining with "||"'),
    # Pipes that bootstrap another shell
    (r'\|\s*sh\b', 'piping into sh'),
    (r'\|\s*bash\b', 'piping into bash'),
    (r'\|\s*zsh\b', 'piping into zsh'),
    (r'\|\s*fish\b', 'piping into fish'),
    (r'\|\s*(?:pwsh|pwsh\.exe|powershell|powershell\.exe)\b', 'piping into PowerShell'),
    # Subshells / secondary evaluation
    (r'\$\(', 'subshell execution with "$()"'),
    (r'`', 'command substitution with backticks'),
    # Redirects to sensitive Unix paths
    (r'>\s*/etc/', 'redirect into /etc'),
    (r'>\s*/dev/sd', 'redirect into block devices'),
    (r'>\s*/dev/hd', 'redirect into block devices'),
    # Backgrounding
    (r'&\s*$', 'background execution'),
    # Explicit destructive Unix commands
    (r'\brm\s+-rf\s+/', 'recursive deletion from filesystem root'),
    (r'\bdd\s+if=', 'disk imaging with dd'),
    (r'\bmkfs\b', 'filesystem formatting with mkfs'),
    (r'\bfdisk\b', 'disk partitioning with fdisk'),
    (r'\bchmod\s+777', 'world-writable chmod'),
    (r'\bchown\s+.*:', 'ownership change with chown'),
]

WINDOWS_DANGEROUS_PATTERNS = [
    (r'\bdel\s+/(?:f|q|s)\b', 'destructive deletion with del'),
    (r'\berase\s+/(?:f|q|s)\b', 'destructive deletion with erase'),
    (r'\brmdir\s+/(?:s|q)\b', 'recursive directory removal with rmdir'),
    (r'\bformat\b', 'disk formatting with format'),
    (r'\bdiskpart\b', 'disk partitioning with diskpart'),
    (r'\breg\s+delete\b', 'registry deletion with reg delete'),
    (r'\b(?:powershell|powershell\.exe|pwsh|pwsh\.exe)\b.*\bremove-item\b.*(?:^|\s)-(?:recurse|r)\b.*(?:^|\s)-(?:force|f)\b', 'forced recursive deletion via PowerShell'),
    (r'\b(?:powershell|powershell\.exe|pwsh|pwsh\.exe)\b.*\b(?:invoke-expression|iex)\b', 'dynamic PowerShell execution'),
    (r'\b(?:stop-computer|restart-computer|shutdown)\b', 'system shutdown or restart'),
]

CONTROL_OPERATORS = {"&&", "||", ";", "|"}
REDIRECTION_OPERATORS = {
    ">",
    ">>",
    "<",
    "<<",
    "1>",
    "1>>",
    "2>",
    "2>>",
    "&>",
    "&>>",
}


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
        # Skill/package CLIs
        "clawhub",
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
        use_rust_core: bool = True,
    ):
        """
        Initialize shell tool.
        
        Args:
            workspace: Working directory for commands
            allowed_commands: List of allowed commands (None = use defaults)
            timeout: Command timeout in seconds
            allow_dangerous: If True, skip pattern checks (still needs whitelist)
            use_rust_core: If True, use Rust bridge fast path when available
        """
        self.workspace = workspace or Path.cwd()
        self.allowed_commands = set(allowed_commands or self.DEFAULT_ALLOWED)
        self.timeout = timeout
        self.allow_dangerous = allow_dangerous
        self.use_rust_core = use_rust_core
        
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
            # Parse command safely. In dangerous/full-exec mode, commands may include
            # shell metacharacters like redirects and chaining operators; those need a
            # platform shell interpreter instead of argv execution.
            args = self._split_command(command)
            base_cmd = self._extract_base_command(args)
            if base_cmd is None:
                return ToolResult(success=False, output="", error="Empty command")
            
            # Find the full path to the command
            cmd_path = shutil.which(base_cmd)
            if cmd_path is None:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command not found: {base_cmd}"
                )

            use_shell = self.allow_dangerous and self._needs_shell_interpreter(args)

            # Hybrid fast-path: execute via Rust core when available and shell syntax
            # is not required.
            if self.use_rust_core and not use_shell:
                rust_result = rust_execute_command_argv(
                    [cmd_path, *args[1:]],
                    str(self.workspace),
                    float(timeout),
                )
                if rust_result is not None:
                    success, returncode, stdout_text, stderr_text, error = rust_result
                    output_parts = []
                    if stdout_text.strip():
                        output_parts.append(stdout_text.strip())
                    if stderr_text.strip():
                        output_parts.append(f"[stderr]\n{stderr_text.strip()}")
                    output = "\n".join(output_parts) if output_parts else "(no output)"
                    return ToolResult(
                        success=success,
                        output=output,
                        error=error or None,
                        data={
                            "returncode": returncode,
                            "command": command,
                            "stdout": stdout_text,
                            "stderr": stderr_text,
                            "engine": "rust",
                        },
                    )
            
            if use_shell:
                shell_argv = self._shell_launcher(command)
                process = await asyncio.create_subprocess_exec(
                    *shell_argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace),
                )
            else:
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
                    "engine": "python",
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

        Pipeline:
        1. Reject empty input.
        2. In safe mode, scan the raw string for dangerous shell syntax and
           known destructive commands. These checks intentionally run before
           tokenization because some shell constructs do not survive argv
           parsing cleanly.
        3. Tokenize the command with OS-appropriate shlex settings.
        4. Apply semantic validation that depends on tokens (inline Python,
           whitelist enforcement, shell-segment extraction).
        
        Returns:
            (is_allowed, error_message)
        """
        if not command or not command.strip():
            return False, "Empty command"
        
        command = command.strip()
        
        if not self.allow_dangerous:
            dangerous_reason = self._match_dangerous_pattern(command)
            if dangerous_reason:
                return False, f"Blocked dangerous command pattern: {dangerous_reason}"
        
        try:
            args = self._split_command(command)
        except ValueError as e:
            return False, f"Invalid command syntax: {e}"

        if not args:
            return False, "Empty command"

        inline_python_error = self._validate_inline_python(args)
        if inline_python_error:
            return False, inline_python_error

        for base_cmd in self._extract_segment_commands(args):
            if base_cmd not in self.allowed_commands:
                allowed_list = ", ".join(sorted(self.allowed_commands)[:10])
                return False, f"Command '{base_cmd}' not allowed. Allowed: {allowed_list}..."
        
        return True, ""

    def _is_windows(self) -> bool:
        return os.name == "nt"

    def _split_command(self, command: str) -> list[str]:
        return shlex.split(command, posix=not self._is_windows())

    def _match_dangerous_pattern(self, command: str) -> Optional[str]:
        patterns = list(RAW_DANGEROUS_PATTERNS)
        if self._is_windows():
            patterns.extend(WINDOWS_DANGEROUS_PATTERNS)
        for pattern, reason in patterns:
            if re.search(pattern, command, flags=re.IGNORECASE):
                return reason
        return None

    def _shell_launcher(self, command: str) -> list[str]:
        if self._is_windows():
            powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")
            if powershell is None:
                raise RuntimeError("PowerShell was not found for full-exec shell mode")
            return [powershell, "-Command", command]
        return ["/bin/bash", "-lc", command]

    def _needs_shell_interpreter(self, args: list[str]) -> bool:
        return any(token in CONTROL_OPERATORS or token in REDIRECTION_OPERATORS for token in args)

    def _extract_base_command(self, args: list[str]) -> Optional[str]:
        commands = self._extract_segment_commands(args)
        return commands[0] if commands else None

    def _extract_segment_commands(self, args: list[str]) -> list[str]:
        commands: list[str] = []
        current: list[str] = []
        skip_next_redirection_target = False

        for token in args:
            if skip_next_redirection_target:
                skip_next_redirection_target = False
                continue

            if token in CONTROL_OPERATORS:
                base = self._first_executable_token(current)
                if base:
                    commands.append(base)
                current = []
                continue

            if token in REDIRECTION_OPERATORS:
                skip_next_redirection_target = True
                continue

            current.append(token)

        base = self._first_executable_token(current)
        if base:
            commands.append(base)
        return commands

    def _first_executable_token(self, tokens: list[str]) -> Optional[str]:
        for token in tokens:
            if token in REDIRECTION_OPERATORS:
                continue
            return token
        return None

    def _validate_inline_python(self, args: list[str]) -> Optional[str]:
        base_cmd = self._extract_base_command(args)
        if base_cmd not in {"python", "python3"}:
            return None
        if "-c" not in args:
            return None
        try:
            code = args[args.index("-c") + 1]
        except IndexError:
            return "Inline Python requires code after -c"
        lowered = code.lower()
        complex_markers = ("\n", ";", " if ", " for ", " while ", " try:", " with ", " def ", " class ", ":")
        if any(marker in lowered for marker in complex_markers):
            return (
                "Complex inline Python via -c is not allowed. "
                "Use a script file, a heredoc-style invocation, or simpler shell commands."
            )
        return None
    
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
