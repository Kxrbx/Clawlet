"""Plugin SDK v2 conformance checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from clawlet.plugins.sdk import SDK_VERSION, PluginTool


@dataclass(slots=True)
class PluginConformanceIssue:
    severity: str  # info | warning | error
    plugin_name: str
    code: str
    message: str
    hint: str


@dataclass(slots=True)
class PluginConformanceReport:
    checked: int
    issues: list[PluginConformanceIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[PluginConformanceIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[PluginConformanceIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[PluginConformanceIssue]:
        return [i for i in self.issues if i.severity == "info"]

    @property
    def passed(self) -> bool:
        return not self.errors


def check_plugin_conformance(tools: Iterable[PluginTool]) -> PluginConformanceReport:
    """Validate plugin tool contracts against SDK v2 compatibility rules."""
    plugins = list(tools)
    report = PluginConformanceReport(checked=len(plugins))
    seen_names: set[str] = set()
    sdk_major = _major(SDK_VERSION)

    for tool in plugins:
        name = str(getattr(tool, "name", "") or "").strip()
        if not name:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name="<unknown>",
                    code="name_missing",
                    message="Plugin tool has empty name",
                    hint="Set ToolSpec(name=...) to a non-empty value",
                )
            )
            continue

        if name in seen_names:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="name_duplicate",
                    message="Duplicate plugin tool name",
                    hint="Ensure each plugin exports unique tool names",
                )
            )
        seen_names.add(name)

        if len(name) > 64:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="name_too_long",
                    message="Tool name exceeds 64 characters",
                    hint="Keep tool names <= 64 chars",
                )
            )

        spec = getattr(tool, "spec", None)
        if spec is None:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="spec_missing",
                    message="Plugin tool missing ToolSpec",
                    hint="Subclass PluginTool and call super().__init__(ToolSpec(...))",
                )
            )
            continue

        sdk_version = str(getattr(spec, "sdk_version", "") or "").strip()
        if not sdk_version:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="sdk_version_missing",
                    message="ToolSpec.sdk_version is missing",
                    hint=f"Set sdk_version to {SDK_VERSION}",
                )
            )
        elif _major(sdk_version) != sdk_major:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="sdk_version_incompatible",
                    message=f"Incompatible sdk_version `{sdk_version}` (expected major {sdk_major})",
                    hint=f"Use SDK v{sdk_major}.x compatible plugin contracts",
                )
            )
        elif sdk_version != SDK_VERSION:
            report.issues.append(
                PluginConformanceIssue(
                    severity="warning",
                    plugin_name=name,
                    code="sdk_version_not_latest",
                    message=f"sdk_version `{sdk_version}` is not latest `{SDK_VERSION}`",
                    hint="Update ToolSpec.sdk_version to current SDK version",
                )
            )

        description = str(getattr(spec, "description", "") or "").strip()
        if not description:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="description_missing",
                    message="ToolSpec.description is empty",
                    hint="Provide a clear ToolSpec.description",
                )
            )

        capabilities = getattr(spec, "capabilities", []) or []
        if not isinstance(capabilities, list) or not all(isinstance(c, str) for c in capabilities):
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="capabilities_invalid",
                    message="ToolSpec.capabilities must be a list of strings",
                    hint="Set capabilities to [] or ['read_only', ...]",
                )
            )

        deprecates = getattr(spec, "deprecates", []) or []
        if not isinstance(deprecates, list) or not all(isinstance(d, str) for d in deprecates):
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="deprecates_invalid",
                    message="ToolSpec.deprecates must be a list of strings",
                    hint="Set deprecates to [] or list of deprecated capability/tool ids",
                )
            )

        # Ensure plugin implements execute_with_context override.
        if type(tool).execute_with_context is PluginTool.execute_with_context:
            report.issues.append(
                PluginConformanceIssue(
                    severity="error",
                    plugin_name=name,
                    code="execute_with_context_not_overridden",
                    message="execute_with_context is not implemented",
                    hint="Implement async execute_with_context(tool_input, context)",
                )
            )

    if report.checked == 0:
        report.issues.append(
            PluginConformanceIssue(
                severity="error",
                plugin_name="<none>",
                code="no_tools",
                message="No plugin tools discovered",
                hint="Export TOOLS = [MyPluginTool()] in plugin.py",
            )
        )

    return report


def _major(version: str) -> int:
    text = (version or "").strip()
    try:
        return int(text.split(".", 1)[0])
    except Exception:
        return -1
