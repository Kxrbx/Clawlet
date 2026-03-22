"""Conversation history trimming and compression helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HistoryTrimmer:
    max_history: int
    logger: Any

    def trim(self, history: list[Any]) -> None:
        """Trim history to prevent unbounded growth while keeping a compressed summary."""
        if len(history) <= self.max_history:
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
            summary_text = "Conversation summary (compressed):\n" + "\n".join(summary_lines)
            summary_msg = type(history[0])(role="system", content=summary_text, metadata={"summary": True})
            tail = list(history[overflow:])
            reserved = 1 + (1 if anchor_msg is not None else 0)
            tail_budget = max(0, self.max_history - reserved)
            rebuilt = [summary_msg]
            if anchor_msg is not None:
                rebuilt.append(anchor_msg)
            rebuilt.extend(tail[-tail_budget:])
            history[:] = self._dedupe_preserved_messages(rebuilt)
        else:
            del history[:-self.max_history]
        self.logger.debug(f"Trimmed history to {len(history)} messages")

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
