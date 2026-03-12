"""Dashboard CLI helpers."""

from __future__ import annotations

import getpass
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

SAKURA_PINK = "#FF69B4"
console = Console()


def run_dashboard_command(
    workspace: Optional[Path],
    port: int,
    frontend_port: int,
    open_browser: bool,
    no_frontend: bool,
    get_workspace_path_fn,
) -> None:
    """Run dashboard command orchestration."""
    workspace_path = workspace or get_workspace_path_fn()
    _ = workspace_path

    api_url = f"http://localhost:{port}"
    frontend_url = f"http://localhost:{frontend_port}"

    print_section("Clawlet Dashboard", "Web UI for your AI agent")
    console.print("|")
    console.print("|  [bold]URLs:[/bold]")
    console.print(f"|    API:      [cyan][link={api_url}]{api_url}[/link][/cyan]")
    console.print(f"|    Frontend: [cyan][link={frontend_url}]{frontend_url}[/link][/cyan]")
    console.print(f"|    Docs:     [cyan][link={api_url}/docs]{api_url}/docs[/link][/cyan]")

    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    frontend_process = None

    if dashboard_dir.exists():
        console.print("|")
        console.print(f"|  [dim]Dashboard directory: {dashboard_dir}[/dim]")
        if not (dashboard_dir / "node_modules").exists():
            console.print("|")
            console.print("|  [yellow]! Frontend dependencies not installed[/yellow]")
            console.print(f"|    Run: [{SAKURA_PINK}]cd {dashboard_dir} && npm install[/{SAKURA_PINK}]")
            console.print("|    Starting API server only...")
            no_frontend = True
    else:
        console.print("|")
        console.print("|  [yellow]! Dashboard directory not found[/yellow]")
        no_frontend = True

    def cleanup_processes():
        if frontend_process and frontend_process.poll() is None:
            console.print("\n[dim]Stopping frontend dev server...[/dim]")
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()

    if not no_frontend and dashboard_dir.exists():
        console.print("|")
        console.print(f"|  [bold]Starting frontend dev server on port {frontend_port}...[/bold]")

        npm_cmd = None
        username = getpass.getuser()
        npm_paths = [
            "C:\\Program Files\\nodejs\\npm.cmd",
            "C:\\Program Files\\nodejs\\npx.cmd",
            "C:\\Program Files\\nodejs\\npm.exe",
            "C:\\Program Files\\nodejs\\npx.exe",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npm.cmd",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npx.cmd",
        ]

        import shutil

        npm_path = shutil.which("npm")
        npx_path = shutil.which("npx")

        if npx_path:
            npm_cmd = [npx_path, "npm", "run", "dev", "--", "--port", str(frontend_port)]
        elif npm_path:
            npm_cmd = [npm_path, "run", "dev", "--", "--port", str(frontend_port)]
        else:
            for item in npm_paths:
                if os.path.exists(item):
                    npm_cmd = [item, "run", "dev", "--", "--port", str(frontend_port)]
                    break

        if npm_cmd is None:
            console.print("|  [yellow]! npm/npx not found, skipping frontend[/yellow]")
            console.print("|    Make sure Node.js is installed and in your PATH")
            console.print("|    Download from: https://nodejs.org")
            no_frontend = True
        else:
            try:
                frontend_process = subprocess.Popen(
                    npm_cmd,
                    cwd=dashboard_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                time.sleep(3)

                if frontend_process.poll() is not None:
                    output = frontend_process.stdout.read() if frontend_process.stdout else ""
                    console.print("|  [red]! Frontend failed to start[/red]")
                    if output:
                        console.print(f"|  [dim]Output: {output[:200]}[/dim]")
                    no_frontend = True
                else:
                    console.print(f"|  [green]OK Frontend dev server started (PID: {frontend_process.pid})[/green]")

            except FileNotFoundError:
                console.print("|  [yellow]! npm not found, skipping frontend[/yellow]")
                console.print("|    Make sure Node.js is installed")
                no_frontend = True
            except Exception as e:
                console.print(f"|  [yellow]! Frontend start error: {e}[/yellow]")
                no_frontend = True

    print_footer()

    if open_browser:
        import webbrowser

        console.print("[dim]Opening browser...[/dim]")
        webbrowser.open(frontend_url)

    console.print()
    console.print(f"[bold green]* Starting API server on port {port}...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    console.print(f"[dim]Python: {sys.executable}[/dim]")
    console.print(f"[dim]Python version: {sys.version.split()[0]}[/dim]")

    try:
        pip_path = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True, timeout=10)
        console.print(f"[dim]pip: {pip_path.stdout.strip()}[/dim]")
    except Exception as e:
        console.print(f"[dim]pip check failed: {e}[/dim]")

    def signal_handler(sig, frame):
        _ = sig, frame
        cleanup_processes()
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        try:
            import uvicorn

            console.print("[dim]uvicorn: found[/dim]")
        except ImportError as e:
            console.print(f"[red]uvicorn: NOT FOUND - {e}[/red]")

        try:
            import fastapi

            _ = fastapi
            console.print("[dim]fastapi: found[/dim]")
        except ImportError as e:
            console.print(f"[red]fastapi: NOT FOUND - {e}[/red]")

        from clawlet.dashboard.api import app

        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError as e:
        cleanup_processes()
        console.print()
        console.print("[red]Error: Dashboard dependencies not installed.[/red]")
        console.print(f"[red]Import error: {e}[/red]")
        console.print()
        console.print("Install with:")
        console.print(f"  [{SAKURA_PINK}]pip install -e '.[dashboard]'[/{SAKURA_PINK}]")
        console.print()
        console.print("Then install the frontend dependencies in:")
        console.print(f"  [{SAKURA_PINK}]dashboard/[/{SAKURA_PINK}] with [{SAKURA_PINK}]npm install[/{SAKURA_PINK}]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        cleanup_processes()
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
