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
from clawlet.tools.web_search import WebSearchTool
from clawlet.tools.skills import InstallSkillTool, ListSkillsTool
from clawlet.tools.memory import MemoryTools
from clawlet.skills.registry import SkillRegistry


FULL_EXEC_COMMANDS = [
    "mkdir", "cp", "mv", "rm", "touch", "chmod", "chown",
    "curl", "wget", "ssh", "scp", "rsync",
    "make", "docker", "kubectl", "terraform",
    "rg",
]

# Convenience alias for all file operations
class FileTool:
    """Composite tool providing all file operations."""
    
    def __init__(self, allowed_dir=None):
        """Initialize all file tools."""
        # Convert string to Path if needed
        from pathlib import Path
        if allowed_dir is not None and not isinstance(allowed_dir, Path):
            allowed_dir = Path(allowed_dir)
        
        self.read = ReadFileTool(allowed_dir)
        self.write = WriteFileTool(allowed_dir)
        self.edit = EditFileTool(allowed_dir)
        self.patch = ApplyPatchTool(allowed_dir)
        self.list = ListDirTool(allowed_dir)
    
    @property
    def tools(self) -> list:
        """Get all file tools."""
        return [self.read, self.write, self.edit, self.patch, self.list]

def create_default_tool_registry(allowed_dir: str = None, config=None, memory_manager=None, skill_registry: SkillRegistry = None) -> ToolRegistry:
    """Create a default tool registry with all standard tools.
    
    Args:
        allowed_dir: Directory to restrict file operations to
        config: Configuration object
        memory_manager: Optional MemoryManager instance for memory tools
        skill_registry: Optional SkillRegistry to register skill tools with
    """
    import logging
    logger = logging.getLogger("clawlet")
    
    logger.info(f"[DEBUG] create_default_tool_registry called with allowed_dir={allowed_dir}")
    
    registry = ToolRegistry()
    
    agent_mode = getattr(getattr(config, "agent", None), "mode", "safe") if config is not None else "safe"
    allow_dangerous = bool(getattr(getattr(config, "agent", None), "shell_allow_dangerous", False)) if config is not None else False
    logger.info(f"[DEBUG] agent_mode={agent_mode}, allow_dangerous={allow_dangerous}")
    effective_allowed_dir = None if agent_mode == "full_exec" else allowed_dir

    # Add file tools
    logger.info("[DEBUG] Creating FileTool...")
    file_tool = FileTool(allowed_dir=effective_allowed_dir)
    logger.info(f"[DEBUG] FileTool created with {len(file_tool.tools)} tools")
    for tool in file_tool.tools:
        logger.info(f"[DEBUG] Registering tool: {tool.name}")
        registry.register(tool)
    
    # Add shell tool (uses 'workspace' parameter, not 'allowed_dir')
    shell_workspace = effective_allowed_dir
    shell_tool = ShellTool(workspace=shell_workspace, allow_dangerous=allow_dangerous)
    if agent_mode == "full_exec":
        shell_tool.add_allowed(*FULL_EXEC_COMMANDS)
        logger.warning("Agent mode is full_exec: expanded shell command capabilities enabled")
    registry.register(shell_tool)

    # Add direct URL fetch tool
    registry.register(FetchUrlTool())

    # Add web search tool (uses Brave Search API)
    # Get API key from config, or check both WEB_SEARCH_API_KEY and BRAVE_SEARCH_API_KEY env vars
    import os
    api_key = None
    web_search_cfg = getattr(config, "web_search", None) if config is not None else None
    if web_search_cfg:
        api_key = web_search_cfg.api_key or os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    else:
        api_key = os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    
    if not api_key:
        logger.warning("WebSearchTool: No API key found. Set WEB_SEARCH_API_KEY or BRAVE_SEARCH_API_KEY environment variable.")
    
    registry.register(WebSearchTool(api_key=api_key))
    
    # Add skill management tools
    registry.register(InstallSkillTool())
    registry.register(ListSkillsTool())
    
    # Add memory tools if memory_manager is provided
    if memory_manager is not None:
        memory_tools = MemoryTools(memory_manager)
        for tool in memory_tools.all_tools():
            registry.register(tool)
        logger.info(f"Registered {len(memory_tools.all_tools())} memory tools")
    
    # Register skill tools if skill_registry is provided
    if skill_registry is not None:
        # Set the tool registry on the skill registry
        skill_registry._tool_registry = registry
        # Register all skill tools
        registered_count = skill_registry.register_tools_with_registry()
        logger.info(f"Registered {registered_count} skill tools from SkillRegistry")
    
    return registry

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "ListDirTool",
    "FileTool",
    "ShellTool",
    "ApplyPatchTool",
    "FetchUrlTool",
    "WebSearchTool",
    "InstallSkillTool",
    "ListSkillsTool",
    "MemoryTools",
    "create_default_tool_registry",
]
