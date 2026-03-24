from __future__ import annotations

from textual.containers import Container
from textual.widgets import Input, Static

from clawlet.tui.models import ApprovalState, LogLine


class LogsPanel(Container):
    def compose(self):
        yield Static("[1] Chat  [2] System  [3] Heartbeat    Filter:", id="logs-tabs")
        yield Input(placeholder="filter logs", id="logs-filter")
        yield Static(id="approval-popup")
        yield Static(id="logs-body")

    def update_logs(self, logs: list[LogLine], active_tab: str, filter_text: str, approval: ApprovalState | None) -> None:
        body = self.query_one("#logs-body", Static)
        popup = self.query_one("#approval-popup", Static)
        tabs = self.query_one("#logs-tabs", Static)
        tabs.update(f"[1] Chat  [2] System  [3] Heartbeat    Active={active_tab.upper()}  Filter:{filter_text or '*'}")
        if approval is not None:
            popup.display = True
            popup.update(
                "\n".join(
                    [
                        "[bold #F59E0B]REQUIRES APPROVAL[/bold #F59E0B]",
                        "For unsafe tool call",
                        f"tool: {approval.tool_name}",
                        f"args: {approval.arguments}",
                        "status: waiting operator",
                        "Options [Y]es [N]o [E]dit args",
                    ]
                )
            )
        else:
            popup.display = False
            popup.update("")
        filtered = []
        for line in logs[-120:]:
            if active_tab != "all" and active_tab != line.channel and not (active_tab == "chat" and line.channel == "chat"):
                if active_tab == "system" and line.channel != "system":
                    continue
                if active_tab == "heartbeat" and line.channel != "heartbeat":
                    continue
            if filter_text and filter_text.lower() not in line.message.lower():
                continue
            filtered.append(f"[{line.timestamp.strftime('%H:%M:%S')}] [{line.level}] {line.message}")
        body.update("[bold #7C3AED]3. SYSTEM LOGS & TELEMETRY[/bold #7C3AED]\n\n" + "\n".join(filtered or ["No logs yet."]))
