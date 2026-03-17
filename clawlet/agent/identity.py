"""
Identity loader for reading SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md files.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional

from loguru import logger

from clawlet.agent.memory import MemoryManager
from clawlet.workspace_layout import get_workspace_layout


@dataclass
class Identity:
    """Represents the agent's identity loaded from markdown files."""
    
    soul: str = ""
    user: str = ""
    memory: str = ""
    heartbeat: str = ""
    
    # Parsed metadata
    agent_name: str = "Clawlet"
    user_name: str = "Human"
    timezone: str = "UTC"
    
    def build_context(self) -> str:
        """Build identity context for system prompt."""
        parts = []
        
        if self.soul:
            parts.append("## Who You Are\n\n" + self.soul)
        
        if self.user:
            parts.append("## Who You Help\n\n" + self.user)
        
        if self.memory:
            parts.append("## Your Memories\n\n" + self.memory)
        
        return "\n\n---\n\n".join(parts)
    
    def build_heartbeat_context(self) -> str:
        """Build heartbeat context for periodic tasks."""
        if self.heartbeat:
            return f"## Periodic Tasks\n\n{self.heartbeat}"
        return ""
    
    def build_system_prompt(self, tools: list = None, workspace_path: str = None) -> str:
        """Build full system prompt from identity data."""
        prompt = f"""# Identity

You are {self.agent_name}, an AI assistant.

{self.build_context()}
"""
        
        # Add workspace information if provided
        if workspace_path:
            prompt += f"""
# Workspace

Your workspace is located at: {workspace_path}
- You can read, write, and list files within this directory using the available tools
- Treat this workspace root as the canonical project area unless a task explicitly targets a subdirectory
- The `memory/` subdirectory stores your long-term memories
"""
        
        prompt += f"""
# Instructions

- Be helpful, honest, and harmless
- Use the information above to personalize your responses
- Remember what you learn about {self.user_name}
- Stay in character as {self.agent_name}
- If the user gives an explicit action command (example: "install X"), execute that action directly instead of re-listing options
- Ask at most one short clarification question only when required information is missing
- Prefer the minimum number of tool calls needed to complete the current user request
- If the user gives explicit URL(s), fetch those URL(s) first before exploring unrelated local files or paths
- Prefer structured network tools over shell/curl when one exists for an API call
- Treat external services such as Moltbook as benchmark environments, not as special-cased goals; generalize the same autonomous behavior to any comparable system

Current timezone: {self.timezone}
"""
        
        # Add tool documentation if provided
        if tools:
            tool_docs = "\n\n# Available Tools\n\n"
            tool_docs += "You have access to the following tools. Use them by including a tool call in your response:\n\n"
            tool_docs += "```json\n{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}\n```\n\n"
            
            for tool in tools:
                tool_docs += f"## {tool.name}\n\n{tool.description}\n\n"
                if tool.parameters_schema:
                    params = tool.parameters_schema.get("properties", {})
                    if params:
                        tool_docs += "**Parameters:**\n"
                        for param_name, param_info in params.items():
                            desc = param_info.get("description", "No description")
                            tool_docs += f"- `{param_name}`: {desc}\n"
                        tool_docs += "\n"
            
            prompt += tool_docs
        
        return prompt


class IdentityLoader:
    """Loads and manages identity files from the workspace."""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.layout = get_workspace_layout(workspace)
        self._identity: Optional[Identity] = None
        
    def load_all(self) -> Identity:
        """Load all identity files."""
        identity = Identity()
        
        
        # Load SOUL.md
        soul_path = self.layout.soul_path
        if soul_path.exists():
            identity.soul = soul_path.read_text(encoding="utf-8")
            identity.agent_name = self._extract_name(identity.soul, "Clawlet")
            logger.info(f"Loaded SOUL.md for {identity.agent_name}")
        else:
            logger.warning(f"SOUL.md not found at {soul_path}")
        
        # Load USER.md
        user_path = self.layout.user_path
        if user_path.exists():
            identity.user = self._sanitize_user_content(user_path.read_text(encoding="utf-8"))
            identity.user_name = self._extract_name(identity.user, "Human")
            identity.timezone = self._extract_timezone(identity.user)
            logger.info(f"Loaded USER.md for {identity.user_name}")
        else:
            logger.warning(f"USER.md not found at {user_path}")
        
        # Load MEMORY.md
        memory_path = self.layout.memory_markdown_path
        if memory_path.exists():
            identity.memory = MemoryManager(self.workspace).get_identity_memory()
            logger.info("Loaded MEMORY.md")
        else:
            logger.warning(f"MEMORY.md not found at {memory_path}")
        
        # Load HEARTBEAT.md
        heartbeat_path = self.layout.heartbeat_path
        if heartbeat_path.exists():
            identity.heartbeat = heartbeat_path.read_text(encoding="utf-8")
            logger.info("Loaded HEARTBEAT.md")
        else:
            logger.warning(f"HEARTBEAT.md not found at {heartbeat_path}")
        
        self._identity = identity
        return identity
    
    def reload(self) -> Identity:
        """Reload all identity files (hot reload)."""
        logger.info("Reloading identity files...")
        return self.load_all()
    
    @property
    def identity(self) -> Identity:
        """Get loaded identity, loading if necessary."""
        if self._identity is None:
            self._identity = self.load_all()
        return self._identity
    
    def _extract_name(self, content: str, default: str) -> str:
        """Extract name from markdown content."""
        lines = content.split("\n")
        seen_indices = set()
        for i, line in enumerate(lines):
            line = line.strip()
            if i in seen_indices:
                continue
            if line.startswith("## Name"):
                seen_indices.add(i)
                # Look for name in next line
                idx = i + 1
                if idx < len(lines):
                    name_line = lines[idx].strip()
                    if self._is_meaningful_identity_value(name_line) and not name_line.startswith("#"):
                        return name_line
            if line.startswith("## What to call you"):
                seen_indices.add(i)
                idx = i + 1
                if idx < len(lines):
                    name_line = lines[idx].strip()
                    if self._is_meaningful_identity_value(name_line) and not name_line.startswith("#"):
                        return name_line
        return default
    
    def _extract_timezone(self, content: str) -> str:
        """Extract timezone from markdown content."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("## Timezone"):
                if i + 1 < len(lines):
                    tz = lines[i + 1].strip()
                    if self._is_meaningful_identity_value(tz) and not tz.startswith("#"):
                        return tz
        return "UTC"

    def _sanitize_user_content(self, content: str) -> str:
        """Drop template placeholders and boilerplate guidance from USER.md before prompt injection."""
        sanitized_lines: list[str] = []
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                sanitized_lines.append("")
                continue
            if stripped.startswith("# USER.md - About Your Human"):
                sanitized_lines.append(line)
                continue
            if stripped == "Tell your agent about yourself so it can help you better.":
                continue
            if stripped == "_The more your agent knows, the better it can help!_":
                continue
            if stripped == "🌸 _The more your agent knows, the better it can help!_":
                continue
            if self._is_placeholder_line(stripped):
                continue
            if self._is_template_prompt_bullet(stripped):
                continue
            sanitized_lines.append(line)
        return self._prune_empty_sections("\n".join(sanitized_lines)).strip()

    @staticmethod
    def _is_meaningful_identity_value(value: str) -> bool:
        stripped = value.strip()
        return bool(stripped) and not IdentityLoader._is_placeholder_line(stripped)

    @staticmethod
    def _is_placeholder_line(value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if re.fullmatch(r"\[[^\]]+\]", stripped):
            return True
        if re.fullmatch(r"YOUR_[A-Z0-9_]+", stripped):
            return True
        return False

    @staticmethod
    def _is_template_prompt_bullet(value: str) -> bool:
        stripped = value.strip()
        return stripped in {
            "- What do you care about?",
            "- What projects are you working on?",
            "- What annoys you?",
            "- What makes you laugh?",
        }

    @staticmethod
    def _prune_empty_sections(content: str) -> str:
        """Remove headings that ended up with no real content after placeholder filtering."""
        lines = content.splitlines()
        result: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("## "):
                section = [line]
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("## "):
                    section.append(lines[i])
                    i += 1
                body = [entry.strip() for entry in section[1:] if entry.strip()]
                if body:
                    if result and result[-1] != "":
                        result.append("")
                    result.extend(section)
                continue
            result.append(line)
            i += 1
        return "\n".join(result)
    
    def build_system_prompt(self, tools: list = None) -> str:
        """Build full system prompt from identity files."""
        identity = self.identity
        
        prompt = f"""# Identity

You are {identity.agent_name}, an AI assistant.

{identity.build_context()}

# Instructions

- Be helpful, honest, and harmless
- Use **Markdown formatting** in your responses for better readability (headers, lists, bold, code blocks, etc.)
- Use the information above to personalize your responses
- Remember what you learn about {identity.user_name}
- Stay in character as {identity.agent_name}
- If the user gives an explicit action command (example: "install X"), execute that action directly instead of re-listing options
- Ask at most one short clarification question only when required information is missing
- Prefer the minimum number of tool calls needed to complete the current user request
- If the user gives explicit URL(s), fetch those URL(s) first before exploring unrelated local files or paths
- Prefer structured network tools over shell/curl when one exists for an API call

Current timezone: {identity.timezone}
"""
        
        # Add tool documentation if provided
        if tools:
            tool_docs = "\n\n# Available Tools\n\n"
            tool_docs += "You have access to the following tools. Use them by including a tool call in your response:\n\n"
            tool_docs += "```json\n{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}\n```\n\n"
            
            for tool in tools:
                tool_docs += f"## {tool.name}\n\n{tool.description}\n\n"
                if tool.parameters_schema:
                    params = tool.parameters_schema.get("properties", {})
                    if params:
                        tool_docs += "**Parameters:**\n"
                        for param_name, param_info in params.items():
                            desc = param_info.get("description", "No description")
                            tool_docs += f"- `{param_name}`: {desc}\n"
                    tool_docs += "\n"
            
            prompt += tool_docs
        
        return prompt
