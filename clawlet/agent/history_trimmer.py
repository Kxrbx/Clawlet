"""Conversation history trimming and compression helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HistoryTrimmer:
    max_history: int
    logger: Any
    max_chars: int = 200_000
    tool_output_cap: int = 2000

    def trim(self, history: list[Any]) -> None:
        """Trim history to prevent unbounded growth while keeping a compressed summary.

        Two thresholds: message count OR total chars. Oversized tool
        outputs are capped in place first (cheapest win, no LLM call).
        """
        self._cap_tool_outputs(history)
        if (
            len(history) <= self.max_history
            and self._total_chars(history) <= self.max_chars
        ):
            return

        overflow = len(history) - self.max_history + 1
        dropped = history[:overflow]
        summary_lines = self._existing_summary_lines(dropped)
        anchor_msg = self._carry_forward_anchor(history, dropped)
        for msg in dropped:
            if msg.role in {"user", "assistant"}:
                excerpt = (msg.content or "").strip().replace("\n", " ")
                if excerpt:
                    summary_lines.append(f"{msg.role}: {excerpt[:180]}")
        if summary_lines:
            if len(summary_lines) > 60:
                summary_lines = summary_lines[:20] + ["..."] + summary_lines[-39:]
            summary_text = "Conversation summary (compressed):\n" + "\n".join(
                summary_lines
            )
            summary_msg = type(history[0])(
                role="system", content=summary_text, metadata={"summary": True}
            )
            tail = list(history[overflow:])
            reserved = 1 + (1 if anchor_msg is not None else 0)
            tail_budget = max(0, self.max_history - reserved)
            rebuilt = [summary_msg]
            if anchor_msg is not None:
                rebuilt.append(anchor_msg)
            rebuilt.extend(tail[-tail_budget:])
            history[:] = self._dedupe_preserved_messages(rebuilt)
        else:
            del history[: -self.max_history]
        self.logger.debug(f"Trimmed history to {len(history)} messages")

    @staticmethod
    def _total_chars(history: list[Any]) -> int:
        return sum(
            len(c)
            for m in history
            if isinstance(c := getattr(m, "content", "") or "", str)
        )

    def _cap_tool_outputs(self, history: list[Any]) -> None:
        """Cap oversized tool outputs in place, preserving metadata."""
        for i, msg in enumerate(history):
            if getattr(msg, "role", "") != "tool":
                continue
            content = getattr(msg, "content", "") or ""
            if not isinstance(content, str) or len(content) <= self.tool_output_cap:
                continue
            history[i] = type(msg)(
                role="tool",
                content=content[: self.tool_output_cap]
                + f"\n[... truncated {len(content) - self.tool_output_cap} chars ...]",
                metadata=getattr(msg, "metadata", {}) or {},
            )

    @staticmethod
    def _existing_summary_lines(messages: list[Any]) -> list[str]:
        """Carry forward prior compressed context instead of dropping it on repeated trims."""
        if not messages:
            return []
        first = messages[0]
        metadata = getattr(first, "metadata", {}) or {}
        if first.role != "system" or metadata.get("summary") is not True:
            return []
        lines = []
        for line in str(getattr(first, "content", "") or "").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned == "Conversation summary (compressed):":
                continue
            lines.append(cleaned)
        return lines

    @staticmethod
    def _carry_forward_anchor(history: list[Any], dropped: list[Any]) -> Any | None:
        if not history:
            return None
        for msg in history[: min(len(history), 3)]:
            metadata = getattr(msg, "metadata", {}) or {}
            if metadata.get("anchor") is True:
                return msg
        for msg in dropped:
            if msg.role == "user" and (msg.content or "").strip():
                metadata = dict(getattr(msg, "metadata", {}) or {})
                metadata["anchor"] = True
                return type(msg)(role=msg.role, content=msg.content, metadata=metadata)
        return None

    @staticmethod
    def _dedupe_preserved_messages(history: list[Any]) -> list[Any]:
        rebuilt: list[Any] = []
        seen_summary = False
        seen_anchor = False
        for msg in history:
            metadata = getattr(msg, "metadata", {}) or {}
            if metadata.get("summary") is True:
                if seen_summary:
                    continue
                seen_summary = True
            if metadata.get("anchor") is True:
                if seen_anchor:
                    continue
                seen_anchor = True
            rebuilt.append(msg)
        return rebuilt
