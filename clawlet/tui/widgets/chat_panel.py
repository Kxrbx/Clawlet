from __future__ import annotations

import json

from textual.widgets import Static

from clawlet.tui.models import TranscriptEntry
from clawlet.tui.theme import CYAN, ERROR, SUCCESS, WARNING


class ChatPanel(Static):
    def update_entries(self, entries: list[TranscriptEntry]) -> None:
        lines: list[str] = ["[bold #7C3AED]1. CHAT & TOOL TRACES[/bold #7C3AED]"]
        for entry in entries[-80:]:
            timestamp = entry.timestamp.strftime("%H:%M:%S")
            if entry.kind == "tool":
                status_color = {"SUCCESS": SUCCESS, "FAILED": ERROR, "REQUIRES APPROVAL": WARNING}.get(entry.status, CYAN)
                lines.append(f"[{timestamp}] [bold]{entry.title}[/bold] [[{status_color}]{entry.status}[/{status_color}]]")
                lines.append(f"  [#06B6D4]{entry.body}[/#06B6D4]")
                raw = entry.metadata.get("raw") or {}
                args = entry.metadata.get("arguments") or {}
                if args:
                    lines.append(f"  args: [#06B6D4]{json.dumps(args, ensure_ascii=False)}[/#06B6D4]")
                if raw:
                    lines.append("  ▼ raw")
                    lines.append(f"  {json.dumps(raw, ensure_ascii=False, indent=2)[:600]}")
            else:
                lines.append(f"[{timestamp}] [bold]{entry.title}[/bold]")
                lines.append(f"{entry.body}")
            lines.append("")
        self.update("\n".join(lines))
