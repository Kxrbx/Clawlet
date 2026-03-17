"""Core runtime models shared across agent execution components."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    """Represents a conversation message."""

    role: str
    content: str
    metadata: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)

    def to_dict(self) -> dict:
        data = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.role == "tool":
            tool_call_id = self.metadata.get("tool_call_id")
            if tool_call_id:
                data["tool_call_id"] = tool_call_id
            tool_name = self.metadata.get("tool_name")
            if tool_name:
                data["name"] = tool_name
        return data


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""

    id: str
    name: str
    arguments: dict


@dataclass
class ConversationState:
    """Per-conversation runtime state."""

    session_id: str
    history: list[Message] = field(default_factory=list)
    summary: str = ""
