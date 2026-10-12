"""Clawlet TUI (Textual).

Agent-interaction patterns — thinking trace, tool chips, approval card,
task rows, streaming answer — are adapted from Beautiful UI
(https://www.beautifului.dev/, MIT © Shane Levine). The upstream sources used
as behavioral references are cached under ``work/beautifului-ref/`` with the
MIT license.
"""

from __future__ import annotations

__all__ = ["ClawletTuiApp", "run_tui_app"]


def __getattr__(name: str):
    if name in {"ClawletTuiApp", "run_tui_app"}:
        from clawlet.tui.app import ClawletTuiApp, run_tui_app

        return {"ClawletTuiApp": ClawletTuiApp, "run_tui_app": run_tui_app}[name]
    raise AttributeError(name)
