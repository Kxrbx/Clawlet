from __future__ import annotations

__all__ = ["ClawletTuiApp", "run_tui_app"]


def __getattr__(name: str):
    if name in {"ClawletTuiApp", "run_tui_app"}:
        from clawlet.tui.app import ClawletTuiApp, run_tui_app

        return {"ClawletTuiApp": ClawletTuiApp, "run_tui_app": run_tui_app}[name]
    raise AttributeError(name)
