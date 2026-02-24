"""
Dashboard command module.
"""

import getpass
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import typer
import webbrowser

from clawlet.cli import SAKURA_PINK, app, console, get_workspace_path, print_section, print_footer


@app.command()
def dashboard(
    workspace: Path = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to run on"),
    frontend_port: int = typer.Option(5173, "--frontend-port", "-f", help="Frontend dev server port"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser automatically"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Don't start frontend dev server"),
):
    """Start the Clawlet dashboard.
    
    Starts both the API server and the React frontend dev server.
    """
    import shutil
    
    workspace_path = workspace or get_workspace_path()
    
    api_url = f"http://localhost:{port}"
    frontend_url = f"http://localhost:{frontend_port}"
    
    print_section("Clawlet Dashboard", "Web UI for your AI agent")
    console.print("│")
    console.print(f"│  [bold]URLs:[/bold]")
    console.print(f"│    API:      [cyan][link={api_url}]{api_url}[/link][/cyan]")
    console.print(f"│    Frontend: [cyan][link={frontend_url}]{frontend_url}[/link][/cyan]")
    console.print(f"│    Docs:     [cyan][link={api_url}/docs]{api_url}/docs[/link][/cyan]")
    
    # Check if frontend is built
    dashboard_dir = Path(__file__).parent.parent.parent / "dashboard"
    frontend_process = None
    
    if dashboard_dir.exists():
        console.print("│")
        console.print(f"│  [dim]Dashboard directory: {dashboard_dir}[/dim]")
        
        # Check for node_modules
        if not (dashboard_dir / "node_modules").exists():
            console.print("│")
            console.print("│  [yellow]! Frontend dependencies not installed[/yellow]")
            console.print(f"│    Run: [{SAKURA_PINK}]cd {dashboard_dir} && npm install[/{SAKURA_PINK}]")
            console.print("│    Starting API server only...")
            no_frontend = True
    else:
        console.print("│")
        console.print("│  [yellow]! Dashboard directory not found[/yellow]")
        no_frontend = True
    
    def cleanup_processes():
        """Clean up subprocesses on exit."""
        if frontend_process and frontend_process.poll() is None:
            console.print("\n[dim]Stopping frontend dev server...[/dim]")
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
    
    # Start frontend dev server
    if not no_frontend and dashboard_dir.exists():
        console.print("│")
        console.print(f"│  [bold]Starting frontend dev server on port {frontend_port}...[/bold]")
        
        # Try to find npm or npx
        npm_cmd = None
        npx_cmd = None
        
        # Check common Windows npm locations
        username = getpass.getuser()
        npm_paths = [
            "C:\\Program Files\\nodejs\\npm.cmd",
            "C:\\Program Files\\nodejs\\npx.cmd",
            "C:\\Program Files\\nodejs\\npm.exe",
            "C:\\Program Files\\nodejs\\npx.exe",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npm.cmd",
            f"C:\\Users\\{username}\\AppData\\Roaming\\npm\\npx.cmd",
        ]
        
        # Try using shutil.which first (respects PATH)
        npm_path = shutil.which("npm")
        npx_path = shutil.which("npx")
        
        console.print(f"[dim]npm path: {npm_path}[/dim]")
        console.print(f"[dim]npx path: {npx_path}[/dim]")
        
        if npx_path:
            # Use npx to run the dev server (it will find npm internally)
            npm_cmd = [npx_path, "npm", "run", "dev", "--", "--port", str(frontend_port)]
            console.print(f"[dim]Using npx: {npm_cmd}[/dim]")
        elif npm_path:
            npm_cmd = [npm_path, "run", "dev", "--", "--port", str(frontend_port)]
            console.print(f"[dim]Using npm: {npm_cmd}[/dim]")
        else:
            # Check common paths
            npm_cmd = None
            for path in npm_paths:
                console.print(f"[dim]Checking: {path}[/dim]")
                if os.path.exists(path):
                    npm_cmd = [path, "run", "dev", "--", "--port", str(frontend_port)]
                    console.print(f"[dim]Found at: {path}[/dim]")
                    break
        
        if npm_cmd is None:
            console.print("│  [yellow]! npm/npx not found, skipping frontend[/yellow]")
            console.print("│    Make sure Node.js is installed and in your PATH")
            console.print("│    Download from: https://nodejs.org")
            no_frontend = True
        else:
            try:
                # Start npm/npx dev server
                frontend_process = subprocess.Popen(
                    npm_cmd,
                    cwd=dashboard_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=0  # Unbuffered
                )
                
                # Wait for frontend to be ready (poll for a few seconds)
                console.print("[dim]Waiting for frontend to start...[/dim]")
                max_wait = 15
                started = False
                for i in range(max_wait):
                    time.sleep(1)
                    
                    # Check if process exited
                    if frontend_process.poll() is not None:
                        # Process exited - check for errors
                        output = frontend_process.stdout.read() if frontend_process.stdout else ""
                        console.print(f"│  [red]! Frontend failed to start[/red]")
                        if output:
                            lines = output.strip().split('\n')[-15:]
                            for line in lines:
                                if line.strip():
                                    console.print(f"│  [dim]  {line}[/dim]")
                        no_frontend = True
                        break
                    
                    # Read any available output
                    if frontend_process.stdout:
                        try:
                            output = frontend_process.stdout.readline()
                            if output:
                                console.print(f"│  [dim]npm: {output.strip()}[/dim]")
                                # Check for Local: URL (might have ANSI codes)
                                if "http://localhost:" in output:
                                    started = True
                                    break
                        except:
                            pass
                
                if not started and frontend_process.poll() is None:
                    console.print(f"│  [green]✓ Frontend dev server started (PID: {frontend_process.pid})[/green]")
                    
            except FileNotFoundError:
                console.print("│  [yellow]! npm not found, skipping frontend[/yellow]")
                console.print("│    Make sure Node.js is installed")
                no_frontend = True
            except Exception as e:
                console.print(f"│  [yellow]! Frontend start error: {e}[/yellow]")
                no_frontend = True
    
    print_footer()
    
    # Open browser if requested and frontend is running
    if open_browser and frontend_process and no_frontend == False:
        console.print(f"[dim]Opening browser to {frontend_url}...[/dim]")
        # Give frontend a moment to be fully ready
        time.sleep(2)
        webbrowser.open(frontend_url)
        console.print(f"[dim]Browser should be open at {frontend_url}[/dim]")
    elif open_browser:
        console.print("[dim]Frontend not running, skipping browser open[/dim]")
    
    # Start the API server
    console.print()
    console.print(f"[bold green]🌸 Starting API server on port {port}...[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()
    
    # Diagnostic info
    console.print(f"[dim]Python: {sys.executable}[/dim]")
    console.print(f"[dim]Python version: {sys.version.split()[0]}[/dim]")
    
    # Get pip location
    try:
        pip_path = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                                   capture_output=True, text=True, timeout=10)
        console.print(f"[dim]pip: {pip_path.stdout.strip()}[/dim]")
    except Exception as e:
        console.print(f"[dim]pip check failed: {e}[/dim]")
    
    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully."""
        cleanup_processes()
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Check which import fails
        try:
            import uvicorn
            console.print("[dim]uvicorn: found[/dim]")
        except ImportError as e:
            console.print(f"[red]uvicorn: NOT FOUND - {e}[/red]")
        
        try:
            import fastapi
            console.print("[dim]fastapi: found[/dim]")
        except ImportError as e:
            console.print(f"[red]fastapi: NOT FOUND - {e}[/red]")
        
        from clawlet.dashboard.api import app as dashboard_app
        
        uvicorn.run(dashboard_app, host="0.0.0.0", port=port)
    except ImportError as e:
        cleanup_processes()
        console.print()
        console.print(f"[red]Error: Dashboard dependencies not installed.[/red]")
        console.print(f"[red]Import error: {e}[/red]")
        console.print()
        console.print("Install with:")
        console.print(f"  [{SAKURA_PINK}]pip install -e '.[dashboard]'[/{SAKURA_PINK}]")
        console.print()
        console.print("Or:")
        console.print(f"  [{SAKURA_PINK}]pip install fastapi uvicorn[/{SAKURA_PINK}]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        cleanup_processes()
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
