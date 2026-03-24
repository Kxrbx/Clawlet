from __future__ import annotations

from textual.containers import Container
from textual.widgets import Input, Static


class FooterPanel(Container):
    def compose(self):
        yield Input(placeholder=">>> Ask Clawlet anything...", id="command-input")
        yield Static("F1 Help   F2 Replay   F3 Raw Context   F4 Export   Q Quit", id="footer-help")
