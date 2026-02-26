"""
Patch tool for applying unified diffs to files in the workspace.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from clawlet.tools.files import _secure_resolve
from clawlet.tools.registry import BaseTool, ToolResult


class ApplyPatchTool(BaseTool):
    """Apply a unified diff patch to a single file."""

    def __init__(self, allowed_dir: Optional[Path] = None):
        self.allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "apply_patch"

    @property
    def description(self) -> str:
        return "Apply a unified diff patch to a file."

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Target file path"},
                "patch": {"type": "string", "description": "Unified diff text"},
            },
            "required": ["path", "patch"],
        }

    async def execute(self, path: str, patch: str, **kwargs) -> ToolResult:
        try:
            target = Path(path)
            resolved_path, error = _secure_resolve(target, self.allowed_dir, must_exist=True)
            if error:
                return ToolResult(success=False, output="", error=error)

            original_lines = resolved_path.read_text(encoding="utf-8").splitlines(keepends=True)
            new_lines = self._apply_unified_diff(original_lines, patch)
            resolved_path.write_text("".join(new_lines), encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Successfully applied patch to {path}",
                data={"path": str(resolved_path), "line_count": len(new_lines)},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _apply_unified_diff(self, src_lines: list[str], diff_text: str) -> list[str]:
        """
        Minimal unified-diff applier supporting @@ hunks for single-file edits.
        """
        lines = diff_text.splitlines()
        hunk_re = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
        out: list[str] = []
        src_idx = 0
        i = 0

        while i < len(lines):
            m = hunk_re.match(lines[i])
            if not m:
                i += 1
                continue

            old_start = int(m.group(1)) - 1
            out.extend(src_lines[src_idx:old_start])
            src_idx = old_start
            i += 1

            while i < len(lines) and not lines[i].startswith("@@"):
                line = lines[i]
                if line.startswith("--- ") or line.startswith("+++ "):
                    i += 1
                    continue
                if not line:
                    token = " "
                    body = ""
                else:
                    token = line[0]
                    body = line[1:]

                if token == " ":
                    expected = src_lines[src_idx].rstrip("\n")
                    if expected != body:
                        raise ValueError("Patch context mismatch")
                    out.append(src_lines[src_idx])
                    src_idx += 1
                elif token == "-":
                    expected = src_lines[src_idx].rstrip("\n")
                    if expected != body:
                        raise ValueError("Patch removal mismatch")
                    src_idx += 1
                elif token == "+":
                    out.append(body + "\n")
                elif token == "\\":
                    pass
                else:
                    raise ValueError(f"Unsupported diff token: {token}")
                i += 1

        out.extend(src_lines[src_idx:])
        return out
