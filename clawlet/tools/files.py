"""
File system tools.
"""

from pathlib import Path
from typing import Optional
from loguru import logger

from clawlet.runtime.rust_bridge import (
    list_dir_entries as rust_list_dir_entries,
    read_text_file as rust_read_text_file,
    write_text_file as rust_write_text_file,
)
from clawlet.tools.registry import BaseTool, ToolResult


def _secure_resolve(
    file_path: Path,
    allowed_dir: Optional[Path],
    must_exist: bool = True,
) -> tuple[Path, Optional[str]]:
    """
    Securely resolve a path, following symlinks and verifying it's within allowed_dir.
    
    Returns:
        tuple: (resolved_path, error_message) - error_message is None if safe
    
    This prevents path traversal attacks via symlinks by:
    1. Using strict=True to ensure the path exists and follows all symlinks
    2. Verifying the final resolved path is still within allowed_dir
    """
    
    if allowed_dir is None:
        if must_exist and not file_path.exists():
            return file_path, f"Path not found: {file_path}"
        return file_path.resolve(strict=must_exist), None
    
    # Ensure allowed_dir is a Path object
    if not isinstance(allowed_dir, Path):
        allowed_dir = Path(allowed_dir)
        logger.debug(f"[_secure_resolve] converted allowed_dir to Path: {allowed_dir}")
    
    try:
        allowed_resolved = allowed_dir.resolve(strict=True)

        # Resolve relative paths from the allowed directory root.
        candidate = file_path if file_path.is_absolute() else (allowed_resolved / file_path)

        if must_exist:
            resolved_path = candidate.resolve(strict=True)
        else:
            if candidate.exists():
                resolved_path = candidate.resolve(strict=True)
            else:
                probe = candidate.parent
                while not probe.exists() and probe != probe.parent:
                    probe = probe.parent
                resolved_parent = probe.resolve(strict=True)
                relative_tail = candidate.parent.relative_to(probe)
                resolved_path = resolved_parent / relative_tail / candidate.name

        try:
            resolved_path.relative_to(allowed_resolved)
        except ValueError:
            return resolved_path, "Access denied: path points outside allowed directory"

        return resolved_path, None

    except FileNotFoundError:
        return file_path, f"Path not found or is a broken symlink: {file_path}"
    except OSError as e:
        # Handle other OS errors (permission issues, circular symlinks, etc.)
        return file_path, f"Path resolution error: {e}"


class ReadFileTool(BaseTool):
    """Tool to read file contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None, use_rust_core: bool = True):
        self.allowed_dir = allowed_dir
        self.use_rust_core = use_rust_core
    
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
            
            if self.use_rust_core:
                rust_result = rust_read_text_file(str(resolved_path))
                if rust_result is not None:
                    ok, content, error = rust_result
                    if not ok:
                        return ToolResult(success=False, output="", error=error or "Read error")
                    return ToolResult(
                        success=True,
                        output=content,
                        data={"path": str(resolved_path), "size": len(content), "engine": "rust"},
                    )

            content = resolved_path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                data={"path": str(resolved_path), "size": len(content), "engine": "python"}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(BaseTool):
    """Tool to write file contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None, use_rust_core: bool = True):
        self.allowed_dir = allowed_dir
        self.use_rust_core = use_rust_core
    
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
            from loguru import logger
            
            file_path = Path(path)
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(file_path, self.allowed_dir, must_exist=False)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            # Create parent directories
            resolved_path.parent.mkdir(parents=True, exist_ok=True)
            
            if self.use_rust_core:
                rust_result = rust_write_text_file(str(resolved_path), content)
                if rust_result is not None:
                    ok, size, error = rust_result
                    if not ok:
                        return ToolResult(success=False, output="", error=error or "Write error")
                    return ToolResult(
                        success=True,
                        output=f"Successfully wrote {size} bytes to {path}",
                        data={"path": str(resolved_path), "size": int(size), "engine": "rust"},
                    )

            resolved_path.write_text(content, encoding="utf-8")
            
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} bytes to {path}",
                data={"path": str(resolved_path), "size": len(content), "engine": "python"}
            )
        except Exception as e:
            from loguru import logger
            logger.error(f"write_file: Failed to write {path}: {e}")
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(BaseTool):
    """Tool to edit file contents with search/replace."""
    
    def __init__(self, allowed_dir: Optional[Path] = None, use_rust_core: bool = True):
        self.allowed_dir = allowed_dir
        self.use_rust_core = use_rust_core
    
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
            from loguru import logger
            engine_used = "python"
            
            file_path = Path(path)
            
            # Security check - use secure resolve to prevent symlink attacks
            resolved_path, error = _secure_resolve(file_path, self.allowed_dir)
            if error:
                return ToolResult(
                    success=False,
                    output="",
                    error=error
                )
            
            if self.use_rust_core:
                rust_result = rust_read_text_file(str(resolved_path))
                if rust_result is not None:
                    ok, content, error = rust_result
                    if not ok:
                        return ToolResult(success=False, output="", error=error or "Read error")
                    engine_used = "rust"
                else:
                    content = resolved_path.read_text()
            else:
                content = resolved_path.read_text()
            
            if old_text not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Text not found in file: {old_text[:50]}..."
                )
            
            new_content = content.replace(old_text, new_text, 1)
            if self.use_rust_core:
                rust_result = rust_write_text_file(str(resolved_path), new_content)
                if rust_result is not None:
                    ok, _, error = rust_result
                    if not ok:
                        return ToolResult(success=False, output="", error=error or "Write error")
                    engine_used = "rust"
                else:
                    resolved_path.write_text(new_content)
            else:
                resolved_path.write_text(new_content)
            
            return ToolResult(
                success=True,
                output=f"Successfully edited {path}",
                data={"path": str(resolved_path), "engine": engine_used}
            )
        except Exception as e:
            from loguru import logger
            logger.error(f"edit_file: Failed to edit {path}: {e}")
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(BaseTool):
    """Tool to list directory contents."""
    
    def __init__(self, allowed_dir: Optional[Path] = None, use_rust_core: bool = True):
        self.allowed_dir = allowed_dir
        self.use_rust_core = use_rust_core
    
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
                    "description": "Path to the directory to list (defaults to current workspace directory)"
                }
            },
            "required": []
        }
    
    async def execute(self, path: str = ".", **kwargs) -> ToolResult:
        """List directory contents."""
        try:
            engine_used = "python"
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
            if self.use_rust_core:
                rust_result = rust_list_dir_entries(str(resolved_path))
                if rust_result is not None:
                    ok, entries, error = rust_result
                    if not ok:
                        return ToolResult(success=False, output="", error=error or "List error")
                    engine_used = "rust"
                    for name, is_dir in entries:
                        item_type = "dir" if is_dir else "file"
                        items.append(f"{name} ({item_type})")
                else:
                    for item in sorted(resolved_path.iterdir()):
                        item_type = "dir" if item.is_dir() else "file"
                        items.append(f"{item.name} ({item_type})")
            else:
                for item in sorted(resolved_path.iterdir()):
                    item_type = "dir" if item.is_dir() else "file"
                    items.append(f"{item.name} ({item_type})")
            
            output = "\n".join(items) if items else "(empty directory)"
            return ToolResult(
                success=True,
                output=output,
                data={"path": str(resolved_path), "count": len(items), "engine": engine_used}
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
