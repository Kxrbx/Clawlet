"""Runtime command helpers for the CLI."""

from __future__ import annotations

import asyncio
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console

from clawlet.workspace_layout import get_workspace_layout

console = Console()


def _agent_pid_path(workspace: Path) -> Path:
    return get_workspace_layout(workspace).agent_pid_path


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        try:
            stat_text = proc_stat.read_text(encoding="utf-8").strip()
            stat_fields = stat_text.split()
            if len(stat_fields) >= 3 and stat_fields[2] == "Z":
                return False
        except Exception:
            pass
    return True


def _read_agent_pid(workspace: Path) -> Optional[int]:
    path = _agent_pid_path(workspace)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _write_agent_pid(workspace: Path) -> None:
    path = _agent_pid_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def _remove_agent_pid(workspace: Path) -> None:
    path = _agent_pid_path(workspace)
    if not path.exists():
        return
    try:
        recorded = int(path.read_text(encoding="utf-8").strip())
    except Exception:
        recorded = None
    if recorded == os.getpid():
        path.unlink(missing_ok=True)


def _build_effective_heartbeat_context(raw_context: str, hb_cfg) -> str:
    """Overlay runtime heartbeat settings onto HEARTBEAT.md-derived context."""
    context = (raw_context or "").strip()
    actionable = False
    for raw_line in context.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("<!--"):
            continue
        actionable = True
        break
    if not actionable:
        return ""
    start = int(getattr(hb_cfg, "quiet_hours_start", 0) or 0)
    end = int(getattr(hb_cfg, "quiet_hours_end", 0) or 0)
    quiet_text = "Disabled" if start == end else f"{start}:00-{end}:00 UTC"

    if "## Quiet Hours" in context:
        context = re.sub(
            r"(?ms)^## Quiet Hours\n.*?(?=^## |\Z)",
            f"## Quiet Hours\n{quiet_text}\n\n",
            context,
        )
    else:
        context = f"{context}\n\n## Quiet Hours\n{quiet_text}".strip()
    return context


def _make_heartbeat_context_loader(workspace: Path, hb_cfg):
    """Read HEARTBEAT.md lazily with a small mtime cache instead of reloading full identity."""
    heartbeat_path = get_workspace_layout(workspace).heartbeat_path
    cache = {"mtime_ns": None, "value": ""}

    def _load() -> str:
        try:
            stat = heartbeat_path.stat()
        except FileNotFoundError:
            cache["mtime_ns"] = None
            cache["value"] = ""
            return ""

        mtime_ns = getattr(stat, "st_mtime_ns", None)
        if cache["mtime_ns"] == mtime_ns:
            return str(cache["value"])

        raw = heartbeat_path.read_text(encoding="utf-8")
        value = _build_effective_heartbeat_context(
            f"## Periodic Tasks\n\n{raw}", hb_cfg
        )
        cache["mtime_ns"] = mtime_ns
        cache["value"] = value
        return value

    return _load


def run_agent_command(
    workspace: Optional[Path],
    model: Optional[str],
    log_file: Optional[Path],
    log_level: str,
    daemon: bool,
    get_workspace_path_fn,
    print_sakura_banner_fn,
    sakura_light: str,
) -> None:
    """Run agent command orchestration."""
    workspace_path = workspace or get_workspace_path_fn()

    if not workspace_path.exists():
        console.print(
            "[red]Error: Workspace not initialized. Run 'clawlet init' first.[/red]"
        )
        raise typer.Exit(1)

    existing_pid = _read_agent_pid(workspace_path)
    if existing_pid and _pid_is_running(existing_pid):
        console.print(
            f"[red]Error: Agent already running with PID {existing_pid}[/red]"
        )
        raise typer.Exit(1)

    effective_log_file = log_file or (workspace_path / "agent.log")

    if daemon and os.environ.get("CLAWLET_AGENT_DAEMON_CHILD") != "1":
        cmd = [
            sys.executable,
            "-m",
            "clawlet",
            "agent",
            "--workspace",
            str(workspace_path),
            "--log-level",
            log_level,
            "--log-file",
            str(effective_log_file),
        ]
        if model:
            cmd.extend(["--model", model])

        env = os.environ.copy()
        env["CLAWLET_AGENT_DAEMON_CHILD"] = "1"
        with open(os.devnull, "wb") as devnull:
            proc = subprocess.Popen(
                cmd,
                cwd=str(Path(__file__).resolve().parents[2]),
                env=env,
                stdin=devnull,
                stdout=devnull,
                stderr=devnull,
                start_new_session=True,
            )
        console.print(f"[green]Agent started in background[/green] (PID {proc.pid})")
        console.print(f"[dim]Log file: {effective_log_file}[/dim]")
        console.print(f"[dim]PID file: {_agent_pid_path(workspace_path)}[/dim]")
        return

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            rotation="10 MB",
            retention="7 days",
            level=log_level.upper(),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        )
        logger.info(f"Logging to file: {log_file}")
    elif daemon:
        effective_log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(effective_log_file),
            rotation="10 MB",
            retention="7 days",
            level=log_level.upper(),
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        )
        logger.info(f"Logging to file: {effective_log_file}")

    if os.environ.get("CLAWLET_AGENT_DAEMON_CHILD") != "1":
        print_sakura_banner_fn()
        console.print(
            f"\n[{sakura_light}]Starting agent...[/{sakura_light}]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]")

    _write_agent_pid(workspace_path)

    try:
        asyncio.run(run_agent(workspace_path, model))
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        _remove_agent_pid(workspace_path)


def run_agent_stop_command(
    workspace: Optional[Path], get_workspace_path_fn, timeout_seconds: float = 10.0
) -> None:
    """Stop a running background agent."""
    workspace_path = workspace or get_workspace_path_fn()
    pid = _read_agent_pid(workspace_path)
    if pid is None:
        console.print("[yellow]Agent is not running (no PID file found).[/yellow]")
        return
    if not _pid_is_running(pid):
        _agent_pid_path(workspace_path).unlink(missing_ok=True)
        console.print(f"[yellow]Removed stale agent PID file for PID {pid}.[/yellow]")
        return

    console.print(f"[dim]Stopping agent PID {pid}...[/dim]")
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        console.print(f"[red]Error stopping agent: {e}[/red]")
        raise typer.Exit(1)

    deadline = time.monotonic() + timeout_seconds
    while _pid_is_running(pid) and time.monotonic() < deadline:
        time.sleep(0.2)

    if _pid_is_running(pid):
        console.print(
            f"[yellow]Agent PID {pid} did not stop after {timeout_seconds:.0f}s. Sending SIGKILL...[/yellow]"
        )
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError as e:
            console.print(f"[red]Error force-stopping agent: {e}[/red]")
            raise typer.Exit(1)

        kill_deadline = time.monotonic() + 5.0
        while _pid_is_running(pid) and time.monotonic() < kill_deadline:
            time.sleep(0.1)

        if _pid_is_running(pid):
            console.print(f"[red]Agent PID {pid} is still running after SIGKILL.[/red]")
            raise typer.Exit(1)

        _agent_pid_path(workspace_path).unlink(missing_ok=True)
        console.print(f"[green]Agent force-stopped[/green] (PID {pid})")
        return

    _agent_pid_path(workspace_path).unlink(missing_ok=True)
    console.print(f"[green]Agent stopped[/green] (PID {pid})")


def run_agent_restart_command(
    workspace: Optional[Path],
    model: Optional[str],
    log_file: Optional[Path],
    log_level: str,
    daemon: bool,
    get_workspace_path_fn,
    print_sakura_banner_fn,
    sakura_light: str,
) -> None:
    """Restart the agent runtime."""
    run_agent_stop_command(
        workspace=workspace, get_workspace_path_fn=get_workspace_path_fn
    )
    run_agent_command(
        workspace=workspace,
        model=model,
        log_file=log_file,
        log_level=log_level,
        daemon=daemon,
        get_workspace_path_fn=get_workspace_path_fn,
        print_sakura_banner_fn=print_sakura_banner_fn,
        sakura_light=sakura_light,
    )


def run_logs_command(log_file: Path, lines: int, follow: bool) -> None:
    """Tail or print agent logs."""
    if not log_file.exists():
        console.print(f"[yellow]Log file not found: {log_file}[/yellow]")
        console.print("Start the agent with --log-file to enable file logging.")
        raise typer.Exit(1)

    try:
        if follow:
            console.print(f"[dim]Following {log_file} (Ctrl+C to stop)...[/dim]")
            try:
                subprocess.run(["tail", "-f", str(log_file)], check=True)
            except FileNotFoundError:
                # tail command not available (e.g., on Windows), use Python implementation
                console.print(
                    "[dim]tail command not found, using Python implementation...[/dim]"
                )
                _follow_logs_python(log_file)
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Error running tail command: {e}[/red]")
        else:
            with open(log_file) as f:
                all_lines = f.readlines()
                start = max(0, len(all_lines) - lines)
                for line in all_lines[start:]:
                    console.print(line.rstrip())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error reading log file: {e}[/red]")
        raise typer.Exit(1)


def _follow_logs_python(log_file: Path) -> None:
    """Follow logs using Python (cross-platform alternative to tail -f)."""
    import time

    with open(log_file, "r") as f:
        # Seek to end of file
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            console.print(line.rstrip())


def _create_provider(config, model: Optional[str]):
    """Create provider from config primary setting."""
    from clawlet.agent.provider_factory import build_provider

    primary = config.provider.primary
    try:
        provider = build_provider(primary, config.provider, model=model or "")
    except ValueError:
        provider = build_provider("openrouter", config.provider, model=model or "")
    return provider, provider.get_default_model()


async def run_agent(workspace: Path, model: Optional[str]):
    """Run the agent loop."""
    from clawlet.agent.identity import IdentityLoader
    from clawlet.agent.loop import AgentLoop
    from clawlet.bus.queue import MessageBus
    from clawlet.config import load_config
    from clawlet.heartbeat.proactive_queue import ProactiveQueueWorker
    from clawlet.heartbeat import Scheduler, create_task_from_config
    from clawlet.heartbeat.runner import HeartbeatRunner
    from clawlet.runtime import build_runtime_services

    identity_loader = IdentityLoader(workspace)
    identity = identity_loader.load_all()
    bus = MessageBus()
    config = load_config(workspace)

    provider, effective_model = _create_provider(config, model)

    services = build_runtime_services(workspace, config)
    memory_manager = services.memory_manager
    tools = services.tools
    logger.info(f"Created tool registry with {len(tools.all_tools())} tools")

    agent = AgentLoop(
        bus=bus,
        workspace=workspace,
        identity=identity,
        provider=provider,
        model=effective_model,
        tools=tools,
        memory_manager=memory_manager,
        max_iterations=config.agent.max_iterations,
        max_tool_calls_per_message=config.agent.max_tool_calls_per_message,
        storage_config=config.storage,
        runtime_config=config.runtime,
    )
    # ponytail: orchestrator sub-agent spawns read provider/profiles from here; without it every delegation fails with "API key required"
    agent.full_config = config

    heartbeat_runner = None
    heartbeat_task = None
    proactive_worker = None
    scheduler = None
    scheduler_task = None
    sched_cfg = config.scheduler
    if getattr(sched_cfg, "enabled", False):
        scheduler = Scheduler(
            timezone=sched_cfg.timezone,
            max_concurrent=sched_cfg.max_concurrent,
            check_interval=float(sched_cfg.check_interval),
            state_file=sched_cfg.state_file,
            jobs_file=sched_cfg.jobs_file,
            runs_dir=sched_cfg.runs_dir,
            message_bus=bus,
            tool_registry=tools,
            skill_registry=None,
        )
        for task_id, task_cfg in sched_cfg.tasks.items():
            scheduler.add_task(create_task_from_config(task_id, task_cfg))
        scheduler_task = asyncio.create_task(scheduler.start())
        logger.info("Scheduler initialized")

    hb_cfg = config.heartbeat
    if getattr(hb_cfg, "proactive_enabled", False):
        proactive_worker = ProactiveQueueWorker(
            bus=bus,
            workspace=workspace,
            queue_path=hb_cfg.proactive_queue_path,
            handoff_dir=hb_cfg.proactive_handoff_dir,
            max_turns_per_hour=hb_cfg.proactive_max_turns_per_hour,
            max_tool_calls_per_cycle=hb_cfg.proactive_max_tool_calls_per_cycle,
        )

    async def _heartbeat_tick_hook(now):
        if scheduler is not None:
            await scheduler.on_heartbeat_tick(now)
        if proactive_worker is not None:
            await proactive_worker.on_heartbeat_tick(now)
        if getattr(hb_cfg, "memory_maintenance", True):
            from clawlet.agent.memory_maintenance import maybe_run_memory_maintenance

            await maybe_run_memory_maintenance(
                memory_manager, workspace_layout.memory_dir, now=now
            )

    heartbeat_loader = _make_heartbeat_context_loader(workspace, hb_cfg)
    workspace_layout = get_workspace_layout(workspace)

    if getattr(hb_cfg, "enabled", False):
        heartbeat_runner = HeartbeatRunner(
            bus=bus,
            interval_minutes=hb_cfg.interval_minutes,
            quiet_hours_start=hb_cfg.quiet_hours_start,
            quiet_hours_end=hb_cfg.quiet_hours_end,
            target=hb_cfg.target,
            ack_max_chars=hb_cfg.ack_max_chars,
            route_provider=agent.get_last_route,
            heartbeat_context_provider=heartbeat_loader,
            state_path=workspace_layout.runtime_dir / "heartbeat_last.json",
            heartbeat_state_path=workspace_layout.heartbeat_state_path,
            on_tick=_heartbeat_tick_hook,
        )
        heartbeat_task = asyncio.create_task(heartbeat_runner.start())
        logger.info("Heartbeat runner initialized")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                shutdown_agent(
                    agent, heartbeat_runner, heartbeat_task, s
                )
            ),
        )

    try:
        await agent.run()
    finally:
        if scheduler is not None:
            await scheduler.stop()
        if scheduler_task is not None:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        if heartbeat_runner is not None:
            heartbeat_runner.stop()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass


async def shutdown_agent(
    agent, heartbeat_runner, heartbeat_task, signum
):
    """Shutdown agent gracefully on signal."""
    logger.info(f"Received signal {signum}, shutting down...")

    agent.stop()

    if heartbeat_runner is not None:
        heartbeat_runner.stop()
    if heartbeat_task is not None:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    await agent.close()
    logger.info("Agent shutdown complete")
