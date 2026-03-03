"""Plugin SDK command helpers for the CLI."""

from __future__ import annotations

import tarfile
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clawlet.cli.common_ui import print_footer, print_section

console = Console()


def run_plugin_init(name: str, directory: Path) -> None:
    """Initialize a plugin SDK v2 skeleton."""
    class_name = name.title().replace("-", "").replace("_", "") + "Tool"
    plugin_dir = (directory / name).resolve()
    plugin_dir.mkdir(parents=True, exist_ok=True)

    plugin_file = plugin_dir / "plugin.py"
    readme_file = plugin_dir / "README.md"

    if not plugin_file.exists():
        plugin_template = (
            f"\"\"\"Example Clawlet plugin: {name}.\"\"\"\n\n"
            "from clawlet.plugins import PluginTool, ToolInput, ToolOutput, ToolSpec\n\n\n"
            f"class {class_name}(PluginTool):\n"
            "    def __init__(self):\n"
            f"        super().__init__(ToolSpec(name=\"{name}\", description=\"Example plugin tool\"))\n\n"
            "    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:\n"
            "        return ToolOutput(output=\"Plugin executed\", data={\"arguments\": tool_input.arguments})\n\n\n"
            f"TOOLS = [{class_name}()]\n"
        )
        plugin_file.write_text(plugin_template, encoding="utf-8")

    if not readme_file.exists():
        readme_file.write_text(
            f"# {name}\n\n"
            "This plugin follows Clawlet Plugin SDK v2.\n\n"
            "Commands:\n"
            f"- `clawlet plugin test --path {plugin_dir}`\n"
            f"- `clawlet plugin publish --path {plugin_dir}`\n",
            encoding="utf-8",
        )

    console.print(f"[green]o Plugin initialized at {plugin_dir}[/green]")


def run_plugin_test(path: Path, strict: bool) -> None:
    """Load and validate a plugin package."""
    from clawlet.plugins.conformance import check_plugin_conformance
    from clawlet.plugins.loader import PluginLoader

    loader = PluginLoader([path])
    tools = loader.load_tools()

    if not tools:
        console.print("[red]No valid plugin tools discovered[/red]")
        raise typer.Exit(1)

    console.print(f"[green]o Loaded {len(tools)} plugin tool(s)[/green]")
    for tool in tools:
        console.print(f"  - {tool.name}: {tool.description}")

    report = check_plugin_conformance(tools)
    if report.issues:
        console.print()
        console.print(f"[bold]Conformance:[/bold] {len(report.issues)} issue(s)")
        for issue in report.issues:
            color = "red" if issue.severity == "error" else ("yellow" if issue.severity == "warning" else "cyan")
            console.print(
                f"[{color}]? {issue.severity.upper()}[/{color}] "
                f"{issue.plugin_name} [{issue.code}] {issue.message}"
            )
            console.print(f"  hint: {issue.hint}")

    if strict and not report.passed:
        raise typer.Exit(2)


def run_plugin_conformance(path: Path) -> None:
    """Run Plugin SDK v2 conformance checks."""
    from clawlet.plugins.conformance import check_plugin_conformance
    from clawlet.plugins.loader import PluginLoader

    loader = PluginLoader([path])
    tools = loader.load_tools()
    report = check_plugin_conformance(tools)

    print_section("Plugin Conformance", f"path={path}")
    console.print(
        "|  "
        f"checked={report.checked} errors={len(report.errors)} "
        f"warnings={len(report.warnings)} infos={len(report.infos)}"
    )
    if report.issues:
        console.print("|")
        for issue in report.issues:
            console.print(
                "|  "
                f"{issue.severity.upper()} {issue.plugin_name} [{issue.code}] {issue.message}"
            )
            console.print(f"|    hint: {issue.hint}")
    print_footer()

    if not report.passed:
        raise typer.Exit(2)


def run_plugin_matrix(
    workspace_path: Path,
    report_path: Optional[Path],
    fail_on_errors: bool,
) -> None:
    """Scan plugin directories and summarize conformance compatibility."""
    from clawlet.config import load_config
    from clawlet.plugins.matrix import run_plugin_conformance_matrix, write_plugin_matrix_report

    try:
        config = load_config(workspace_path)
        plugin_dirs = []
        for raw_dir in config.plugins.directories:
            p = Path(raw_dir).expanduser()
            if not p.is_absolute():
                p = workspace_path / p
            plugin_dirs.append(p)
    except Exception:
        plugin_dirs = [workspace_path / "plugins"]

    report = run_plugin_conformance_matrix(plugin_dirs)
    print_section("Plugin Matrix", f"workspace={workspace_path}")
    console.print(
        "|  "
        f"directories={report.scanned_directories} tools={report.scanned_tools} "
        f"errors={report.total_errors} warnings={report.total_warnings} infos={report.total_infos}"
    )
    if report.results:
        console.print("|")
        for item in report.results:
            console.print(
                "|  "
                f"{item.directory}: tools={item.loaded_tools} "
                f"errors={item.errors} warnings={item.warnings} "
                f"passed={'yes' if item.passed else 'no'}"
            )
    output = report_path or (workspace_path / "plugin-matrix-report.json")
    write_plugin_matrix_report(output, report)
    console.print(f"|  Report: {output}")
    print_footer()

    if fail_on_errors and not report.passed:
        raise typer.Exit(2)


def run_plugin_publish(path: Path, out_dir: Path) -> None:
    """Package a plugin directory as a distributable tarball."""
    if not path.exists() or not path.is_dir():
        console.print("[red]Invalid plugin path[/red]")
        raise typer.Exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{path.name}-{int(time.time())}.tar.gz"

    with tarfile.open(archive, "w:gz") as tar:
        tar.add(path, arcname=path.name)

    console.print(f"[green]o Packaged plugin archive: {archive}[/green]")
