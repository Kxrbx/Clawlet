"""
File system tools.
"""

from pathlib import Path
from typing import Optional

from clawlet.tools.registry import BaseTool, ToolResult


def _secure_resolve(file_path: Path, allowed_dir: Optional[Path]) -> tuple[Path, Optional[str]]:
    """
    Securely resolve a path, following symlinks and verifying it's within allowed_dir.
    
    Returns:
        tuple: (resolved_path, error_message) - error_message is None if safe
    
    This prevents path traversal attacks via symlinks by:
    1. Using strict=True to ensure the path exists and follows all symlinks
    2. Verifying the final resolved path is still within allowed_dir
    """
    # DEBUG: Log allowed_dir type
    from loguru import logger
    logger.debug(f"[_secure_resolve] allowed_dir: {allowed_dir} (type: {type(allowed_dir)})")
    # END DEBUG
    
    if allowed_dir is None:
        return file_path, None
    
    try:
        # Resolve with strict=True to follow all symlinks and ensure path exists
        # This will raise FileNotFoundError if the path doesn't exist (including broken symlinks)
        resolved_path = file_path.resolve(strict=True)
        
        # Get the allowed_dir resolved path
        allowed_resolved = allowed_dir.resolve()
        
        # Check if resolved path is within allowed_dir
        resolved_str = str(resolved_path)
        allowed_str = str(allowed_resolved)
        
        # Ensure the resolved path starts with allowed_dir
        if not resolved_str.startswith(allowed_str):
            return resolved_path, f"Access denied: symlink points outside allowed directory"
        
        return resolved_path, None
        
    except FileNotFoundError:
        # This handles broken symlinks or non-existent paths
        return file_path, f"Path not found or is a broken symlink: {file_path}"
    except OSError as e:
        # Handle other OS errors (permission issues, circular symlinks, etc.)
        return file_path, f"Path resolution error: {e}"


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
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(file_path, self.allowed_dir)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            content = resolved_path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                data={"path": str(resolved_path), "size": len(content)}
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
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(file_path, self.allowed_dir)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            # Create parent directories
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            resolved_path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} bytes to {path}",
                data={"path": str(resolved_path), "size": len(content)}
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
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(file_path, self.allowed_dir)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            content = resolved_path.read_text()
            
            if old_text not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Text not found in file: {old_text[:50]}..."
                )
            
            new_content = content.replace(old_text, new_text, 1)
            resolved_path.write_text(new_content)
            
            return ToolResult(
                success=True,
                output=f"Successfully edited {path}",
                data={"path": str(resolved_path)}
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
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(dir_path, self.allowed_dir)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            if not resolved_path.is_dir():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a directory: {path}"
                )
            
            items = []
            for item in sorted(resolved_path.iterdir()):
                item_type = "dir" if item.is_dir() else "file"
                items.append(f"{item.name} ({item_type})")
            
            output = "\n".join(items) if items else "(empty directory)"
            return ToolResult(
                success=True,
                output=output,
                data={"path": str(resolved_path), "count": len(items)}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
