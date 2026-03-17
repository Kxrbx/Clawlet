"""Approval flow state and user-facing metadata helpers."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(slots=True)
class PendingApproval:
    token: str
    tool_call: object


@dataclass(slots=True)
class ApprovalService:
    pending: dict[str, PendingApproval] = field(default_factory=dict)

    @staticmethod
    def convo_key(channel: str, chat_id: str) -> str:
        return f"{channel}:{chat_id}"

    @staticmethod
    def mint_token() -> str:
        return str(int(time.time()))[-6:]

    def get(self, convo_key: str) -> Optional[PendingApproval]:
        return self.pending.get(convo_key)

    def set(self, convo_key: str, token: str, tool_call: object) -> None:
        self.pending[convo_key] = PendingApproval(token=token, tool_call=tool_call)

    def clear(self, convo_key: str) -> None:
        self.pending.pop(convo_key, None)

    def snapshot(self, convo_key: str) -> dict:
        pending = self.pending.get(convo_key)
        if not pending:
            return {}
        tool_call = pending.tool_call
        return {
            "token": pending.token,
            "tool_call": tool_call,
        }

    def peek(self, channel: str, chat_id: str) -> Optional[dict]:
        pending = self.pending.get(self.convo_key(channel, chat_id))
        if not pending:
            return None
        tool_call = pending.tool_call
        return {
            "token": pending.token,
            "tool_name": getattr(tool_call, "name", ""),
            "arguments": dict(getattr(tool_call, "arguments", {}) or {}),
        }

    def format_tool_call_details(self, tool_call: object) -> str:
        try:
            args = json.dumps(getattr(tool_call, "arguments", {}) or {}, indent=2, ensure_ascii=True, sort_keys=True)
        except Exception:
            args = str(getattr(tool_call, "arguments", {}) or {})
        return f"Tool: {getattr(tool_call, 'name', '')}\nArguments:\n{args}"

    def build_confirmation_outbound_metadata(self, token: str, tool_call: object, reason: str) -> dict:
        details = self.format_tool_call_details(tool_call)
        return {
            "telegram_buttons": [
                [
                    {"text": "Approve", "callback_data": f"approval:approve:{token}"},
                    {"text": "Reject", "callback_data": f"approval:reject:{token}"},
                ],
                [
                    {"text": "Show details", "callback_data": f"approval:details:{token}"},
                ],
            ],
            "telegram_pending_approval": {
                "token": token,
                "tool_name": getattr(tool_call, "name", ""),
                "reason": reason,
                "arguments": dict(getattr(tool_call, "arguments", {}) or {}),
                "details": details,
            },
        }

    async def maybe_handle_confirmation_reply(
        self,
        *,
        convo_key: str,
        user_message: str,
        execute_tool: Callable[[object], object],
        render_tool_result: Callable[[object], str],
        append_tool_message: Callable[[str, object], None],
    ) -> Optional[str]:
        pending = self.pending.get(convo_key)
        if not pending:
            return None

        text = user_message.strip().lower()
        if text in {"cancel", "cancel it", "abort"}:
            self.clear(convo_key)
            return "Cancelled the pending action."

        m = re.match(r"confirm\s+(\d{4,8})$", text)
        if not m:
            return None

        token = m.group(1)
        if token != pending.token:
            return "Confirmation token does not match the pending action."

        tc = pending.tool_call
        result = await execute_tool(tc)
        rendered = render_tool_result(result)
        append_tool_message(rendered, tc)
        self.clear(convo_key)

        if getattr(result, "success", False):
            return f"Confirmed and executed `{getattr(tc, 'name', '')}`.\n\n{getattr(result, 'output', '')}"
        return (
            f"Confirmed but `{getattr(tc, 'name', '')}` failed: "
            f"{getattr(result, 'error', '') or getattr(result, 'output', '')}"
        )
