"""Approval modal for unsafe tool calls."""

from __future__ import annotations

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from clawlet.tui.models import ApprovalState


class ApprovalModal(ModalScreen[bool]):
    """Y/N confirmation dialog. Dismisses with True (approve) or False (cancel)."""

    def __init__(self, approval: ApprovalState):
        super().__init__()
        self.approval = approval

    def compose(self) -> ComposeResult:
        with Container(id="approval-box"):
            yield Static("REQUIRES APPROVAL", classes="warning-title")
            yield Static(f"tool: {escape(self.approval.tool_name)}", classes="approval-tool")
            yield Static(f"reason: {escape(self.approval.reason)}")
            args = json.dumps(self.approval.arguments, ensure_ascii=False, indent=2)[:800]
            yield Static(f"args:\n{escape(args)}")
            yield Static(f"token: {escape(self.approval.token)}")
            with Horizontal():
                yield Button("Yes [y]", variant="warning", id="approve-yes")
                yield Button("No [n]", variant="default", id="approve-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve-yes")

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "y":
            self.dismiss(True)
        elif key in {"n", "escape"}:
            self.dismiss(False)
