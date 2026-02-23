"""
Tools module - Agent capabilities.

Available tools:
- ReadFileTool: Read file contents
- WriteFileTool: Write file contents
- EditFileTool: Edit files with search/replace
- ListDirTool: List directory contents
- ShellTool: Execute shell commands (safe)
- WebSearchTool: Search the web via Brave API
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
from clawlet.tools.web_search import WebSearchTool

# Convenience alias for all file operations
class FileTool:
    """Composite tool providing all file operations."""
    
    def __init__(self, allowed_dir=None):
        """Initialize all file tools."""
        self.read = ReadFileTool(allowed_dir)
        self.write = WriteFileTool(allowed_dir)
        self.edit = EditFileTool(allowed_dir)
        self.list = ListDirTool(allowed_dir)
    
    @property
    def tools(self) -> list:
        """Get all file tools."""
        return [self.read, self.write, self.edit, self.list]

def create_default_tool_registry(allowed_dir: str = None, config=None) -> ToolRegistry:
    """Create a default tool registry with all standard tools."""
    import os
    
    registry = ToolRegistry()
    
    # Add file tools
    file_tool = FileTool(allowed_dir=allowed_dir)
    for tool in file_tool.tools:
        registry.register(tool)
    
    # Add shell tool (uses 'workspace' parameter, not 'allowed_dir')
    registry.register(ShellTool(workspace=allowed_dir))
    
    # Add web search tool (uses Brave Search API)
    # Get API key from config, or check both WEB_SEARCH_API_KEY and BRAVE_SEARCH_API_KEY env vars
    api_key = None
    if config and config.web_search:
        api_key = config.web_search.api_key or os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    else:
        api_key = os.environ.get("WEB_SEARCH_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    
    if not api_key:
        logger.warning("WebSearchTool: No API key found. Set WEB_SEARCH_API_KEY or BRAVE_SEARCH_API_KEY environment variable.")
    
    registry.register(WebSearchTool(api_key=api_key))
    
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
    "WebSearchTool",
    "create_default_tool_registry",
]
