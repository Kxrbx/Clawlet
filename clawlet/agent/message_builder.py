"""Provider message assembly for agent turns."""

from __future__ import annotations

import json
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

    async def build_messages(
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
            memory_context = await self.memory.get_context(
                max_entries=max(6, min(12, self.context_window)),
                query=query_text,
            )
            if memory_context:
                messages.append({"role": "system", "content": memory_context})
        except Exception as e:
            self.logger.debug(f"Memory context unavailable for this turn: {e}")

        recent_history = history[-self.context_window :]
        summary_message = None
        anchor_message = None
        if history and history[0].role == "system" and history[0].metadata.get("summary") is True:
            summary_message = history[0]
            messages.append(summary_message.to_dict())
        for msg in history[: min(len(history), 3)]:
            if getattr(msg, "metadata", {}).get("anchor") is True:
                anchor_message = msg
                break
        if anchor_message is not None and anchor_message is not summary_message:
            messages.append(anchor_message.to_dict())

        for msg in recent_history:
            if summary_message is not None and msg is summary_message:
                continue
            if anchor_message is not None and msg is anchor_message:
                continue
            msg_dict = self._sanitize_message_for_provider(msg.to_dict())
            if msg.role == "tool" and not msg_dict.get("tool_call_id"):
                self.logger.warning(
                    f"Skipping tool message without tool_call_id: {msg.content[:50]}..."
                )
                continue
            messages.append(msg_dict)

        return messages

    def _sanitize_message_for_provider(self, msg_dict: dict) -> dict:
        sanitized = dict(msg_dict or {})
        tool_calls = sanitized.get("tool_calls")
        if not isinstance(tool_calls, list):
            return sanitized

        rewritten_calls: list[dict] = []
        for call in tool_calls:
            if not isinstance(call, dict):
                rewritten_calls.append(call)
                continue
            rewritten = dict(call)
            function = rewritten.get("function")
            if not isinstance(function, dict):
                rewritten_calls.append(rewritten)
                continue
            fn = dict(function)
            name = str(fn.get("name", "") or "").strip()
            raw_arguments = fn.get("arguments")
            if name != "http_request" or not isinstance(raw_arguments, str):
                rewritten["function"] = fn
                rewritten_calls.append(rewritten)
                continue
            try:
                parsed_args = json.loads(raw_arguments)
            except Exception:
                rewritten["function"] = fn
                rewritten_calls.append(rewritten)
                continue
            if not isinstance(parsed_args, dict):
                rewritten["function"] = fn
                rewritten_calls.append(rewritten)
                continue
            sanitized_args = self._sanitize_http_request_history_args(parsed_args)
            if sanitized_args != parsed_args:
                fn["arguments"] = json.dumps(sanitized_args, ensure_ascii=False)
            rewritten["function"] = fn
            rewritten_calls.append(rewritten)

        sanitized["tool_calls"] = rewritten_calls
        return sanitized

    def _sanitize_http_request_history_args(self, parsed_args: dict) -> dict:
        cleaned = json.loads(json.dumps(parsed_args))

        def _clean(value):
            if isinstance(value, dict):
                updated = {}
                for key, item in value.items():
                    cleaned_item = _clean(item)
                    if cleaned_item is _DROP:
                        continue
                    updated[key] = cleaned_item
                return updated
            if isinstance(value, list):
                updated = []
                for item in value:
                    cleaned_item = _clean(item)
                    if cleaned_item is _DROP:
                        continue
                    updated.append(cleaned_item)
                return updated
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"the live value", "live value", "your_api_key", "placeholder", "<your_api_key>"}:
                    return _DROP
            return value

        cleaned = _clean(cleaned)
        if not isinstance(cleaned, dict):
            return {}

        headers = cleaned.get("headers")
        if isinstance(headers, dict):
            auth_value = str(headers.get("Authorization", "") or "")
            lowered_auth = auth_value.strip().lower()
            if any(token in lowered_auth for token in {"the live value", "your_api_key", "<your_api_key>", "bearer placeholder"}):
                headers.pop("Authorization", None)
            if not headers:
                cleaned.pop("headers", None)

        auth_profile = str(cleaned.get("auth_profile", "") or "").strip().lower()
        if auth_profile in {"the live value", "live value"}:
            cleaned.pop("auth_profile", None)

        return cleaned


_DROP = object()
