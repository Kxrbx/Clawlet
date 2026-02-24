"""
Identity loader for reading SOUL.md, USER.md, MEMORY.md, HEARTBEAT.md files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


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
    
    def build_system_prompt(self, tools: list = None) -> str:
        """Build full system prompt from identity data."""
        prompt = f"""# Identity

You are {self.agent_name}, an AI assistant.

{self.build_context()}

# Instructions

- Be helpful, honest, and harmless
- Use the information above to personalize your responses
- Remember what you learn about {self.user_name}
- Stay in character as {self.agent_name}

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
        self._identity: Optional[Identity] = None
        
    def load_all(self) -> Identity:
        """Load all identity files."""
        identity = Identity()
        
        # DEBUG: Log that we're loading identity files
        logger.info("[DEBUG] Loading identity files from workspace")
        # END DEBUG
        
        # Load SOUL.md
        soul_path = self.workspace / "SOUL.md"
        if soul_path.exists():
            identity.soul = soul_path.read_text(encoding="utf-8")
            identity.agent_name = self._extract_name(identity.soul, "Clawlet")
            logger.info(f"Loaded SOUL.md for {identity.agent_name}")
        else:
            logger.warning(f"SOUL.md not found at {soul_path}")
        
        # Load USER.md
        user_path = self.workspace / "USER.md"
        if user_path.exists():
            identity.user = user_path.read_text(encoding="utf-8")
            identity.user_name = self._extract_name(identity.user, "Human")
            identity.timezone = self._extract_timezone(identity.user)
            logger.info(f"Loaded USER.md for {identity.user_name}")
        else:
            logger.warning(f"USER.md not found at {user_path}")
        
        # Load MEMORY.md
        memory_path = self.workspace / "MEMORY.md"
        if memory_path.exists():
            identity.memory = memory_path.read_text(encoding="utf-8")
            logger.info("Loaded MEMORY.md")
        else:
            logger.warning(f"MEMORY.md not found at {memory_path}")
        
        # Load HEARTBEAT.md
        heartbeat_path = self.workspace / "HEARTBEAT.md"
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
            # DEBUG: Log that we're loading from scratch
            logger.info("[DEBUG] Identity cache is empty, loading identity files")
            self._identity = self.load_all()
        else:
            # DEBUG: Log that we're using cached identity
            logger.info("[DEBUG] Using cached identity (files may have changed on disk)")
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
                    if name_line and not name_line.startswith("#"):
                        return name_line
            if line.startswith("## What to call you"):
                seen_indices.add(i)
                idx = i + 1
                if idx < len(lines):
                    name_line = lines[idx].strip()
                    if name_line and not name_line.startswith("#"):
                        return name_line
        return default
    
    def _extract_timezone(self, content: str) -> str:
        """Extract timezone from markdown content."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith("## Timezone"):
                if i + 1 < len(lines):
                    tz = lines[i + 1].strip()
                    if tz and not tz.startswith("#"):
                        return tz
        return "UTC"
    
    def build_system_prompt(self, tools: list = None) -> str:
        """Build full system prompt from identity files."""
        identity = self.identity
        
        prompt = f"""# Identity

You are {identity.agent_name}, an AI assistant.

{identity.build_context()}

# Instructions

- Be helpful, honest, and harmless
- Use the information above to personalize your responses
- Remember what you learn about {identity.user_name}
- Stay in character as {identity.agent_name}

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
