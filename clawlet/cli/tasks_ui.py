"""Tasks UI — inspect per-task orchestration profiles and routing."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from clawlet.agent.task_profiles import TASK_KINDS, resolve_profile
from clawlet.agent.task_router import classify

console = Console()


def _load_profiles(workspace_path: Path) -> tuple[dict, str, object | None]:
    """Load (task_profiles dict, global_provider, provider_config) from workspace config."""
    from clawlet.config import load_config

    try:
        config = load_config(workspace_path)
    except Exception:
        config = None
    profiles: dict = {}
    global_provider = "openrouter"
    provider_config = None
    if config is not None:
        raw = getattr(config, "task_profiles", None) or {}
        for k, v in raw.items():
            profiles[k] = v
        provider_config = getattr(config, "provider", None)
        if provider_config is not None:
            global_provider = (
                getattr(provider_config, "primary", "openrouter") or "openrouter"
            )
    return profiles, global_provider, provider_config


def run_tasks_list_command(*, workspace_path: Path, as_json: bool = False) -> None:
    """List resolved execution profiles for every task kind."""
    profiles, global_provider, _ = _load_profiles(workspace_path)
    rows = []
    for kind in TASK_KINDS:
        resolved = resolve_profile(kind, profiles, global_provider=global_provider)
        rows.append(resolved.as_dict())
    if as_json:
        console.print_json(json.dumps(rows, indent=2, default=str))
        return
    table = Table(title="Task profiles (resolved)")
    for col in ("kind", "provider", "model", "toolset", "iters", "tools", "timeout"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r["kind"],
            r["provider"],
            r["model"] or "(global default)",
            r["toolset"],
            str(r["max_iterations"]),
            str(r["tool_call_limit"]),
            f"{r['timeout_s']:.0f}s",
        )
    console.print(table)


def run_tasks_show_command(
    *, workspace_path: Path, kind: str, as_json: bool = False
) -> None:
    """Show the resolved profile for one task kind."""
    profiles, global_provider, _ = _load_profiles(workspace_path)
    resolved = resolve_profile(kind, profiles, global_provider=global_provider)
    data = resolved.as_dict()
    if as_json:
        console.print_json(json.dumps(data, indent=2, default=str))
        return
    for key, value in data.items():
        console.print(f"[bold]{key}[/bold]: {value}")


def run_tasks_test_routing_command(*, text: str, as_json: bool = False) -> None:
    """Classify a sample message without touching the network (rules pass)."""
    result = asyncio.run(classify(text))
    payload = {
        "text": text,
        "kind": result.kind,
        "confidence": result.confidence,
        "reason": result.reason,
        "source": result.source,
    }
    if as_json:
        console.print_json(json.dumps(payload, indent=2))
        return
    console.print(
        f"kind=[bold]{result.kind}[/bold] confidence={result.confidence:.2f} ({result.reason})"
    )
