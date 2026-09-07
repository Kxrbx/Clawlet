"""
Tools module - Agent capabilities.

Available tools:
- ReadFileTool: Read file contents
- WriteFileTool: Write file contents
- EditFileTool: Edit files with search/replace
- ListDirTool: List directory contents
- ShellTool: Execute shell commands (safe)
- FetchUrlTool: Fetch and extract content from direct URLs
- WebSearchTool: Search the web via Brave API
- InstallSkillTool: Install skills from GitHub URLs
- ListSkillsTool: List installed skills
"""

from pathlib import Path
from typing import TYPE_CHECKING

from clawlet.tools.registry import (
    BaseTool,
    ToolRegistry,
    ToolResult,
)
from clawlet.tools.files import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    ListDirTool,
)
from clawlet.tools.shell import ShellTool
from clawlet.tools.patch import ApplyPatchTool
from clawlet.tools.fetch_url import FetchUrlTool
from clawlet.tools.http_request import HttpRequestTool
from clawlet.tools.web_search import WebSearchTool
from clawlet.tools.skills import InstallSkillTool, ListSkillsTool
from clawlet.tools.memory import MemoryTools
from clawlet.tools.assembly import (
    register_file_and_shell_tools,
    register_memory_tools,
    register_network_tools,
    register_skill_tools,
)
if TYPE_CHECKING:
    from clawlet.skills.registry import SkillRegistry


FULL_EXEC_COMMANDS = [
    "mkdir", "cp", "mv", "rm", "touch", "chmod", "chown",
    "curl", "wget", "ssh", "scp", "rsync",
    "make", "docker", "kubectl", "terraform",
    "rg",
]

def create_default_tool_registry(
    allowed_dir: str = None,
    config=None,
    memory_manager=None,
    skill_registry: "SkillRegistry" = None,
) -> ToolRegistry:
    """Create a default tool registry with all standard tools.
    
    Args:
        allowed_dir: Directory to restrict file operations to
        config: Configuration object
        memory_manager: Optional MemoryManager instance for memory tools
        skill_registry: Optional SkillRegistry to register skill tools with
    """
    registry = ToolRegistry()
    register_file_and_shell_tools(registry, allowed_dir=allowed_dir, config=config)
    register_network_tools(registry, allowed_dir=allowed_dir, config=config)
    register_skill_tools(registry, skill_registry=skill_registry)
    register_memory_tools(registry, memory_manager=memory_manager)
    return registry

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirTool",
    "ShellTool",
    "ApplyPatchTool",
    "FetchUrlTool",
    "HttpRequestTool",
    "WebSearchTool",
    "InstallSkillTool",
    "ListSkillsTool",
    "MemoryTools",
    "create_default_tool_registry",
]
