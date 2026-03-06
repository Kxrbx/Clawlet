"""Queue-backed proactive heartbeat worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Optional

from loguru import logger

from clawlet.bus.queue import InboundMessage, MessageBus
from clawlet.metrics import get_metrics

UTC = timezone.utc


@dataclass
class QueueItem:
    line_no: int
    raw: str
    text: str
    priority: int


class ProactiveQueueWorker:
    """Dispatches autonomous queue work on heartbeat ticks."""

    def __init__(
        self,
        bus: MessageBus,
        workspace: Path,
        queue_path: str = "tasks/QUEUE.md",
        handoff_dir: str = "memory/proactive",
        max_turns_per_hour: int = 4,
        max_tool_calls_per_cycle: int = 3,
    ):
        self.bus = bus
        self.workspace = workspace
        self.queue_path = queue_path
        self.handoff_dir = handoff_dir
        self.max_turns_per_hour = max(1, int(max_turns_per_hour))
        self.max_tool_calls_per_cycle = max(1, int(max_tool_calls_per_cycle))
        self._dispatches: list[datetime] = []

    async def on_heartbeat_tick(self, now: datetime) -> int:
        """Process one queue item if guardrails allow."""
        if not self._allow_dispatch(now):
            return 0
        item = self._select_next_item()
        if item is None:
            return 0

        prompt = (
            "Proactive queue task triggered from heartbeat.\n"
            f"Work on this item now: {item.text}\n"
            f"Hard limit: at most {self.max_tool_calls_per_cycle} tool calls this cycle.\n"
            "After completion, summarize what was done and any blockers."
        )
        try:
            await self.bus.publish_inbound(
                InboundMessage(
                    channel="scheduler",
                    chat_id="main",
                    content=prompt,
                    user_id="proactive",
                    user_name="ProactiveQueue",
                    metadata={
                        "source": "heartbeat",
                        "heartbeat": True,
                        "proactive": True,
                        "queue_item": item.text,
                        "max_tool_calls_per_cycle": self.max_tool_calls_per_cycle,
                    },
                )
            )
        except Exception as e:
            logger.warning(f"Proactive queue dispatch failed for '{item.text}': {e}")
            return 0

        claimed = self._mark_item_done(item)
        if not claimed:
            logger.warning(
                f"Proactive queue dispatch sent but item could not be marked done: {item.text}"
            )
            return 1

        self._dispatches.append(now)
        get_metrics().inc_proactive_tasks_completed()
        self._append_handoff(now=now, item=item)
        logger.info(f"Proactive queue dispatched: {item.text}")
        return 1

    def _allow_dispatch(self, now: datetime) -> bool:
        window_start = now - timedelta(hours=1)
        self._dispatches = [ts for ts in self._dispatches if ts >= window_start]
        return len(self._dispatches) < self.max_turns_per_hour

    def _queue_file(self) -> Path:
        queue_file = Path(self.queue_path)
        if not queue_file.is_absolute():
            queue_file = self.workspace / queue_file
        return queue_file

    def _select_next_item(self) -> Optional[QueueItem]:
        queue_file = self._queue_file()
        if not queue_file.exists():
            return None
        lines = queue_file.read_text(encoding="utf-8").splitlines()
        candidates: list[QueueItem] = []
        for idx, line in enumerate(lines):
            m = re.match(r"^\s*-\s*\[\s\]\s*(.*)$", line)
            if not m:
                continue
            text = m.group(1).strip()
            prio = 2
            if text.startswith("[P1]"):
                prio = 1
                text = text[4:].strip()
            elif text.startswith("[P2]"):
                prio = 2
                text = text[4:].strip()
            elif text.startswith("[P3]"):
                prio = 3
                text = text[4:].strip()
            candidates.append(QueueItem(line_no=idx, raw=line, text=text, priority=prio))
        if not candidates:
            return None
        candidates.sort(key=lambda c: (c.priority, c.line_no))
        return candidates[0]

    def _mark_item_done(self, item: QueueItem) -> bool:
        queue_file = self._queue_file()
        if not queue_file.exists():
            return False
        lines = queue_file.read_text(encoding="utf-8").splitlines()
        if item.line_no >= len(lines):
            return False
        lines[item.line_no] = re.sub(r"\[\s\]", "[x]", lines[item.line_no], count=1)
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True

    def _append_handoff(self, now: datetime, item: QueueItem) -> None:
        handoff_root = Path(self.handoff_dir)
        if not handoff_root.is_absolute():
            handoff_root = self.workspace / handoff_root
        handoff_root.mkdir(parents=True, exist_ok=True)
        target = handoff_root / f"{now.date().isoformat()}.md"
        line = f"- {now.isoformat()} proactive-dispatch: {item.text}\n"
        with open(target, "a", encoding="utf-8") as f:
            f.write(line)
