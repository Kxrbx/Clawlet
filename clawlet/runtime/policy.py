"""Runtime policy engine for tool execution authorization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from clawlet.runtime.types import ToolExecutionMode


READ_ONLY_TOOLS = {
    "read_file",
    "list_dir",
    "web_search",
    "fetch_url",
    "list_skills",
    "recall_memory",
    "search_memory",
}

WRITE_TOOLS = {
    "write_file",
    "edit_file",
    "apply_patch",
    "remember",
    "forget",
    "install_skill",
}

_ELEVATED_PATTERNS = [
    re.compile(r"\brm\b"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\bchown\b"),
    re.compile(r"\bgit\s+reset\b"),
    re.compile(r"\bgit\s+clean\b"),
    re.compile(r"\bdd\b"),
    re.compile(r"\bmkfs\b"),
]


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class RuntimePolicyEngine:
    """Simple policy engine with mode-based authorization."""

    def __init__(
        self,
        default_mode: ToolExecutionMode = "workspace_write",
        allowed_modes: tuple[ToolExecutionMode, ...] = ("read_only", "workspace_write"),
        require_approval_for: tuple[ToolExecutionMode, ...] = ("elevated",),
    ):
        self.default_mode = default_mode
        self.allowed_modes = set(allowed_modes)
        self.require_approval_for = set(require_approval_for)

    def infer_mode(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionMode:
        """Infer execution mode from tool intent and arguments."""
        name = (tool_name or "").strip().lower()
        if name in READ_ONLY_TOOLS:
            return "read_only"
        if name in WRITE_TOOLS:
            return "workspace_write"
        if name == "shell":
            cmd = str(arguments.get("command", "")).strip().lower()
            if any(p.search(cmd) for p in _ELEVATED_PATTERNS):
                return "elevated"
            return "workspace_write"
        return self.default_mode

    def authorize(self, mode: ToolExecutionMode, approved: bool = False) -> PolicyDecision:
        """Authorize an execution mode."""
        if mode not in self.allowed_modes and mode != "elevated":
            return PolicyDecision(False, f"Mode '{mode}' is not allowed by runtime policy")

        if mode == "elevated" and mode in self.require_approval_for and not approved:
            return PolicyDecision(False, "Elevated mode requires explicit approval")

        if mode == "elevated" and "elevated" not in self.allowed_modes and not approved:
            return PolicyDecision(False, "Elevated mode is disabled")

        return PolicyDecision(True, "")
