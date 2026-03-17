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
        summary_lines = []
        for msg in dropped:
            if msg.role in {"user", "assistant"}:
                excerpt = (msg.content or "").strip().replace("\n", " ")
                if excerpt:
                    summary_lines.append(f"{msg.role}: {excerpt[:180]}")
        if summary_lines:
            summary_text = "Conversation summary (compressed):\n" + "\n".join(summary_lines[-20:])
            summary_msg = type(history[0])(role="system", content=summary_text, metadata={"summary": True})
            history[:] = [summary_msg] + history[overflow:]
        else:
            del history[:-self.max_history]
        self.logger.debug(f"Trimmed history to {len(history)} messages")
