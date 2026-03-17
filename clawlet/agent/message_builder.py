"""Provider message assembly for agent turns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(slots=True)
class MessageBuilder:
    identity: Any
    tools: Any
    workspace: Any
    context_engine: Any
    memory: Any
    heartbeat_state: Any
    context_window: int
    heartbeat_action_policy: str
    logger: Any

    def build_messages(
        self,
        history: list[Any],
        *,
        query_hint: Optional[str] = None,
        is_heartbeat: bool = False,
        heartbeat_metadata: Optional[dict] = None,
    ) -> list[dict]:
        messages: list[dict] = []
        tools_list = self.tools.all_tools() if self.tools else None
        system_prompt = self.identity.build_system_prompt(
            tools=tools_list,
            workspace_path=str(self.workspace),
        )
        messages.append({"role": "system", "content": system_prompt})

        metadata = heartbeat_metadata or {}
        if is_heartbeat:
            messages.append({"role": "system", "content": self.heartbeat_action_policy})
            heartbeat_summary = str(metadata.get("heartbeat_state_summary", "") or "").strip()
            if not heartbeat_summary:
                heartbeat_summary = self.heartbeat_state.build_prompt_summary()
            if heartbeat_summary:
                messages.append({"role": "system", "content": heartbeat_summary})

        query_text = (query_hint or "").strip()
        if not query_text:
            for msg in reversed(history):
                if msg.role == "user" and msg.content:
                    query_text = msg.content
                    break

        if query_text and not is_heartbeat:
            try:
                repo_context = self.context_engine.render_for_prompt(
                    query=query_text,
                    max_files=5,
                    char_budget=3000,
                )
                if repo_context:
                    messages.append({"role": "system", "content": repo_context})
            except Exception as e:
                self.logger.debug(f"Context engine unavailable for this turn: {e}")

        try:
            memory_context = self.memory.get_context(
                max_entries=max(6, min(12, self.context_window)),
                query=query_text,
            )
            if memory_context:
                messages.append({"role": "system", "content": memory_context})
        except Exception as e:
            self.logger.debug(f"Memory context unavailable for this turn: {e}")

        recent_history = history[-self.context_window :]
        summary_message = None
        if history and history[0].role == "system" and history[0].metadata.get("summary") is True:
            summary_message = history[0]
            messages.append(summary_message.to_dict())

        for msg in recent_history:
            if summary_message is not None and msg is summary_message:
                continue
            msg_dict = msg.to_dict()
            if msg.role == "tool" and not msg_dict.get("tool_call_id"):
                self.logger.warning(
                    f"Skipping tool message without tool_call_id: {msg.content[:50]}..."
                )
                continue
            messages.append(msg_dict)

        return messages
