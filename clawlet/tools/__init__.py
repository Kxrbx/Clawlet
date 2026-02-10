"""
Tools module - Agent capabilities.

Available tools:
- FileTool: Read, write, list files
- ShellTool: Execute shell commands (safe)
- WebSearchTool: Search the web via Brave API
"""

from clawlet.tools.registry import (
    BaseTool,
    ToolRegistry,
    ToolResult,
)
from clawlet.tools.files import FileTool
from clawlet.tools.shell import ShellTool
from clawlet.tools.web_search import WebSearchTool

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "FileTool",
    "ShellTool",
    "WebSearchTool",
]
