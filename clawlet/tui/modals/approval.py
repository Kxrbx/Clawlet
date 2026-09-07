"""Approval modal for unsafe tool calls (Beautiful UI ApprovalCard -> Textual).

The dialog names the exact pending action, the target and consequences, and
makes the safe escape explicit: denying means the tool is NOT run and the
agent continues without it.
"""

from __future__ import annotations

import json

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from clawlet.tui.models import ApprovalState


class ApprovalModal(ModalScreen[bool]):
    """Approve/deny confirmation dialog. Dismisses with True (approve) or False (deny)."""

    def __init__(self, approval: ApprovalState):
        super().__init__()
        self.approval = approval

    def compose(self) -> ComposeResult:
        with Container(id="approval-box"):
            yield Static("REQUIRES APPROVAL", classes="warning-title")
            yield Static(f"Approve tool: {escape(self.approval.tool_name)}", classes="approval-tool")
            if self.approval.reason:
                yield Static(f"Reason: {escape(self.approval.reason)}")
            args = json.dumps(self.approval.arguments, ensure_ascii=False, indent=2)
            if args.strip() not in ("{}", ""):
                yield Static(f"Arguments:\n{escape(args[:800])}", classes="approval-args")
            yield Static(
                "Approve → the tool runs now.  Deny → Clawlet skips it and continues.",
                classes="approval-consequence",
            )
            yield Static(f"token: {escape(self.approval.token)}", classes="approval-token")
            with Horizontal():
                yield Button("Approve [y]", variant="warning", id="approve-yes")
                yield Button("Deny [n]", variant="default", id="approve-no")

    def on_mount(self) -> None:
        # Safe default: denial requires a deliberate choice.
        self.query_one("#approve-no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve-yes")

    def on_key(self, event) -> None:
        key = event.key.lower()
        if key == "y":
            self.dismiss(True)
        elif key in {"n", "escape"}:
            self.dismiss(False)