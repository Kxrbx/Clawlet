from __future__ import annotations

from textual.widgets import Static

from clawlet.tui.models import BrainState


class BrainPanel(Static):
    def update_state(self, state: BrainState) -> None:
        total = max(1, state.context_max_tokens)
        used = max(0, state.context_used_tokens)
        pct = int((used / total) * 100)
        filled = max(1 if used else 0, int(24 * used / total))
        bar = "█" * filled + "░" * max(0, 24 - filled)
        memory = "\n".join(f"{k}={v}" for k, v in state.memory[:8]) or "n/a"
        tools = "\n".join(f"{name:<18} {status}" for name, status in state.tools[:10]) or "n/a"
        self.update(
            "\n".join(
                [
                    "[bold #7C3AED]2. THE BRAIN STATE[/bold #7C3AED]",
                    "[dim]AGENT STATE & CONTEXT[/dim]",
                    "",
                    "Context Window",
                    f"[{bar}] {used} / {total} Tokens ({pct}%)",
                    "",
                    "Memory",
                    memory,
                    "",
                    "Tools",
                    tools,
                    "",
                    f"Status: [bold]{state.status}[/bold]",
                    f"Provider: {state.provider}",
                    f"Model: {state.model}",
                ]
            )
        )
