"""
File system tools.
"""

from pathlib import Path
from typing import Optional

from clawlet.tools.registry import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Tool to read file contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file from the filesystem."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        """Read a file."""
        try:
            file_path = Path(path)
            
            # Security check
            if self.allowed_dir and not str(file_path.resolve()).startswith(str(self.allowed_dir.resolve())):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Access denied: path outside allowed directory"
                )
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}"
                )
            
            content = file_path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                data={"path": str(file_path), "size": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(BaseTool):
    """Tool to write file contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file on the filesystem."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs) -> ToolResult:
        """Write a file."""
        try:
            file_path = Path(path)
            
            # Security check
            if self.allowed_dir and not str(file_path.resolve()).startswith(str(self.allowed_dir.resolve())):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Access denied: path outside allowed directory"
                )
            
            # Create parent directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} bytes to {path}",
                data={"path": str(file_path), "size": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(BaseTool):
    """Tool to edit file contents with search/replace."""
    
    def __init__(self, allowed_dir: Optional[Path] = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing specific text with new text."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "Text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, **kwargs) -> ToolResult:
        """Edit a file."""
        try:
            file_path = Path(path)
            
            # Security check
            if self.allowed_dir and not str(file_path.resolve()).startswith(str(self.allowed_dir.resolve())):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Access denied: path outside allowed directory"
                )
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}"
                )
            
            content = file_path.read_text()
            
            if old_text not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Text not found in file: {old_text[:50]}..."
                )
            
            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content)
            
            return ToolResult(
                success=True,
                output=f"Successfully edited {path}",
                data={"path": str(file_path)}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(BaseTool):
    """Tool to list directory contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "List the contents of a directory."
    
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, **kwargs) -> ToolResult:
        """List directory contents."""
        try:
            dir_path = Path(path)
            
            # Security check
            if self.allowed_dir and not str(dir_path.resolve()).startswith(str(self.allowed_dir.resolve())):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Access denied: path outside allowed directory"
                )
            
            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Directory not found: {path}"
                )
            
            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a directory: {path}"
                )
            
            items = []
            for item in sorted(dir_path.iterdir()):
                item_type = "dir" if item.is_dir() else "file"
                items.append(f"{item.name} ({item_type})")
            
            output = "\n".join(items) if items else "(empty directory)"
            return ToolResult(
                success=True,
                output=output,
                data={"path": str(dir_path), "count": len(items)}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
