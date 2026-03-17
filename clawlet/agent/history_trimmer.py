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
            history[:] = [summary_msg] + history[overflow:]
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
