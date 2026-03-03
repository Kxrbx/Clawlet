"""Sessions command helpers for the CLI."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

console = Console()


def run_sessions_command(workspace_path: Path, export: Optional[Path], limit: int) -> None:
    """List and optionally export conversation sessions from storage."""
    config_path = workspace_path / "config.yaml"
    if not config_path.exists():
        console.print("[red]Config file not found[/red]")
        raise typer.Exit(1)

    try:
        import aiosqlite
        from clawlet.config import Config
        from clawlet.storage.postgres import PostgresStorage
        from clawlet.storage.sqlite import SQLiteStorage

        config = Config.from_yaml(config_path)

        if config.storage.backend == "sqlite":
            db_path = Path(config.storage.sqlite.path).expanduser()
            storage = SQLiteStorage(db_path)
        elif config.storage.backend == "postgres":
            pg = config.storage.postgres
            storage = PostgresStorage(
                host=pg.host,
                port=pg.port,
                database=pg.database,
                user=pg.user,
                password=pg.password,
            )
        else:
            console.print(f"[red]Unsupported storage backend: {config.storage.backend}[/red]")
            raise typer.Exit(1)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if hasattr(storage, "initialize"):
            loop.run_until_complete(storage.initialize())
        else:
            loop.run_until_complete(storage.connect())

        if config.storage.backend == "sqlite":

            async def get_recent_sessions():
                async with aiosqlite.connect(db_path) as db:
                    cursor = await db.execute(
                        """
                        SELECT session_id, COUNT(*) as msg_count, MAX(created_at) as last_seen
                        FROM messages
                        GROUP BY session_id
                        ORDER BY last_seen DESC
                        LIMIT ?
                    """,
                        (limit,),
                    )
                    rows = await cursor.fetchall()
                    return rows

            rows = loop.run_until_complete(get_recent_sessions())
        else:
            rows = loop.run_until_complete(storage.list_sessions(limit=limit))

        if not rows:
            console.print("[dim]No sessions found[/dim]")
        else:
            print_section("Recent Sessions", f"Showing up to {limit} sessions")
            for session_id, count, last_seen in rows:
                console.print(f"|  {session_id[:12]}...  [{count} messages]  last: {last_seen}")
            print_footer()

        if export:
            if config.storage.backend == "sqlite":

                async def export_all():
                    async with aiosqlite.connect(db_path) as db:
                        cursor = await db.execute("SELECT * FROM messages ORDER BY created_at DESC")
                        rows = await cursor.fetchall()
                        cols = [desc[0] for desc in cursor.description]
                        return [dict(zip(cols, row)) for row in rows]

                all_msgs = loop.run_until_complete(export_all())
                export.write_text(json.dumps(all_msgs, indent=2))
                console.print(f"[green]o Exported {len(all_msgs)} messages to {export}[/green]")
            else:
                all_msgs = loop.run_until_complete(storage.export_messages())
                export.write_text(json.dumps(all_msgs, indent=2))
                console.print(f"[green]o Exported {len(all_msgs)} messages to {export}[/green]")

        loop.run_until_complete(storage.close())
        loop.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
