"""Transcript export for the TUI (runs inside a Textual worker)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from clawlet.tui.models import TranscriptEntry


def default_export_path(workspace: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return workspace / f"transcript-{stamp}.md"


def write_transcript_markdown(path: Path, entries: list[TranscriptEntry], session_id: str) -> Path:
    """Write transcript entries to markdown. Returns the path written."""
    lines = [f"# Clawlet transcript — session `{session_id}`", ""]
    for entry in entries:
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append(f"## {entry.title} · {ts}")
        if entry.status:
            lines.append(f"*status: {entry.status}*")
        lines.append("")
        lines.append(entry.body)
        args = entry.metadata.get("arguments")
        if args:
            lines.append("")
            lines.append(f"args: `{args}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
