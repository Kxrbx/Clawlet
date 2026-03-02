"""Plugin conformance matrix across multiple plugin directories."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from clawlet.plugins.conformance import PluginConformanceReport, check_plugin_conformance
from clawlet.plugins.loader import PluginLoader


@dataclass(slots=True)
class PluginDirectoryResult:
    directory: str
    loaded_tools: int
    passed: bool
    errors: int
    warnings: int
    infos: int


@dataclass(slots=True)
class PluginMatrixReport:
    scanned_directories: int
    scanned_tools: int
    directories_with_errors: int
    total_errors: int
    total_warnings: int
    total_infos: int
    results: list[PluginDirectoryResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total_errors == 0

    def to_dict(self) -> dict:
        return {
            "scanned_directories": self.scanned_directories,
            "scanned_tools": self.scanned_tools,
            "directories_with_errors": self.directories_with_errors,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "total_infos": self.total_infos,
            "passed": self.passed,
            "results": [asdict(item) for item in self.results],
        }


def run_plugin_conformance_matrix(directories: list[Path]) -> PluginMatrixReport:
    results: list[PluginDirectoryResult] = []
    scanned_tools = 0
    dirs_with_errors = 0
    total_errors = 0
    total_warnings = 0
    total_infos = 0

    for directory in directories:
        loader = PluginLoader([directory])
        tools = loader.load_tools()
        scanned_tools += len(tools)
        report: PluginConformanceReport = check_plugin_conformance(tools)

        errors = len(report.errors)
        warnings = len(report.warnings)
        infos = len(report.infos)
        total_errors += errors
        total_warnings += warnings
        total_infos += infos
        if errors > 0:
            dirs_with_errors += 1

        results.append(
            PluginDirectoryResult(
                directory=str(directory),
                loaded_tools=len(tools),
                passed=report.passed,
                errors=errors,
                warnings=warnings,
                infos=infos,
            )
        )

    return PluginMatrixReport(
        scanned_directories=len(directories),
        scanned_tools=scanned_tools,
        directories_with_errors=dirs_with_errors,
        total_errors=total_errors,
        total_warnings=total_warnings,
        total_infos=total_infos,
        results=results,
    )


def write_plugin_matrix_report(path: Path, report: PluginMatrixReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")


def run_plugin_matrix_smokecheck(workdir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    root = workdir / "plugin-matrix-smoke"
    good = root / "good"
    bad = root / "bad"
    good.mkdir(parents=True, exist_ok=True)
    bad.mkdir(parents=True, exist_ok=True)

    (good / "plugin.py").write_text(
        "from clawlet.plugins import PluginTool, ToolInput, ToolOutput, ToolSpec\n"
        "class GoodTool(PluginTool):\n"
        "    def __init__(self):\n"
        "        super().__init__(ToolSpec(name='good_tool', description='good'))\n"
        "    async def execute_with_context(self, tool_input: ToolInput, context) -> ToolOutput:\n"
        "        return ToolOutput(output='ok')\n"
        "TOOLS=[GoodTool()]\n",
        encoding="utf-8",
    )
    (bad / "plugin.py").write_text(
        "from clawlet.plugins import PluginTool, ToolSpec\n"
        "class BadTool(PluginTool):\n"
        "    def __init__(self):\n"
        "        super().__init__(ToolSpec(name='bad_tool', description='bad', sdk_version='1.0.0'))\n"
        "TOOLS=[BadTool()]\n",
        encoding="utf-8",
    )

    report = run_plugin_conformance_matrix([good, bad])
    if report.scanned_directories != 2:
        errors.append("expected 2 scanned directories")
    if report.scanned_tools < 2:
        errors.append("expected at least 2 loaded tools")
    if report.total_errors <= 0:
        errors.append("expected conformance errors from bad plugin")

    return len(errors) == 0, errors
