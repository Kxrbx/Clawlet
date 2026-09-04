"""Config migration analysis helpers for legacy workspace compatibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class MigrationIssue:
    severity: str  # info | warning | error
    path: str
    message: str
    hint: str
    can_autofix: bool = False


@dataclass(slots=True)
class ConfigMigrationReport:
    config_path: str
    issues: list[MigrationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[MigrationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[MigrationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[MigrationIssue]:
        return [i for i in self.issues if i.severity == "info"]

    @property
    def has_blockers(self) -> bool:
        return bool(self.errors)


def analyze_config_migration(config_path: Path) -> ConfigMigrationReport:
    """Analyze config for legacy keys and migration opportunities."""
    report = ConfigMigrationReport(config_path=str(config_path))
    if not config_path.exists():
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="config.yaml",
                message="Config file not found",
                hint="Run `clawlet init` to generate config.yaml",
                can_autofix=False,
            )
        )
        return report

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="config.yaml",
                message=f"Invalid YAML: {e}",
                hint="Fix YAML syntax before running migration validation",
                can_autofix=False,
            )
        )
        return report

    if not isinstance(raw, dict):
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="config.yaml",
                message="Top-level config must be an object",
                hint="Rewrite config.yaml as a mapping of sections",
                can_autofix=False,
            )
        )
        return report

    _check_legacy_channel_shape(raw, report)
    _check_legacy_agent_keys(raw, report)
    _check_provider_shape(raw, report)
    _check_unknown_top_level(raw, report)

    return report


def summarize_migration_hints(report: ConfigMigrationReport, max_items: int = 10) -> list[str]:
    """Create short user-facing migration hint lines from an analysis report."""
    hints: list[str] = []
    for issue in report.issues[: max(1, int(max_items))]:
        hints.append(f"{issue.severity.upper()} {issue.path}: {issue.message}. Hint: {issue.hint}")
    return hints




def _load_raw(config_path: Path) -> tuple[Any, str]:
    if not config_path.exists():
        return None, "Config file not found"
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        return None, f"Invalid YAML: {e}"
    return raw, ""




def _check_legacy_channel_shape(raw: dict[str, Any], report: ConfigMigrationReport) -> None:
    legacy_channel_keys = ("telegram", "discord", "whatsapp", "slack")
    for key in legacy_channel_keys:
        if key in raw:
            report.issues.append(
                MigrationIssue(
                    severity="warning",
                    path=key,
                    message=f"Legacy root-level channel key `{key}` detected",
                    hint=f"Move `{key}` under `channels.{key}`",
                    can_autofix=True,
                )
            )

    channels = raw.get("channels")
    if channels is not None and not isinstance(channels, dict):
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="channels",
                message="`channels` must be an object",
                hint="Set `channels` to a map with keys like telegram/discord",
                can_autofix=False,
            )
        )


def _check_legacy_agent_keys(raw: dict[str, Any], report: ConfigMigrationReport) -> None:
    agent = raw.get("agent")
    if not isinstance(agent, dict):
        return

    if "full_exec" in agent:
        report.issues.append(
            MigrationIssue(
                severity="warning",
                path="agent.full_exec",
                message="Legacy key `agent.full_exec` is deprecated",
                hint="Use `agent.mode: full_exec|safe` instead",
                can_autofix=True,
            )
        )

    if "execution_mode" in agent:
        report.issues.append(
            MigrationIssue(
                severity="warning",
                path="agent.execution_mode",
                message="Legacy key `agent.execution_mode` is deprecated",
                hint="Use `agent.mode` instead",
                can_autofix=True,
            )
        )


def _check_provider_shape(raw: dict[str, Any], report: ConfigMigrationReport) -> None:
    provider = raw.get("provider")
    if not isinstance(provider, dict):
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="provider",
                message="`provider` section is missing or invalid",
                hint="Set `provider.primary` and corresponding provider config",
                can_autofix=False,
            )
        )
        return

    primary = str(provider.get("primary") or "").strip()
    if not primary:
        report.issues.append(
            MigrationIssue(
                severity="error",
                path="provider.primary",
                message="`provider.primary` is required",
                hint="Set provider.primary to openrouter/openai/anthropic/...",
                can_autofix=False,
            )
        )
        return

    if primary not in {"ollama", "lmstudio"} and provider.get(primary) is None:
        report.issues.append(
            MigrationIssue(
                severity="warning",
                path=f"provider.{primary}",
                message=f"`provider.primary` is `{primary}` but `provider.{primary}` block is missing",
                hint=f"Add `provider.{primary}` configuration block",
                can_autofix=False,
            )
        )


def _check_unknown_top_level(raw: dict[str, Any], report: ConfigMigrationReport) -> None:
    known = {
        "provider",
        "channels",
        "storage",
        "agent",
        "heartbeat",
        "scheduler",
        "web_search",
        "runtime",
        "benchmarks",
        "plugins",
        # legacy keys handled separately
        "telegram",
        "discord",
        "whatsapp",
        "slack",
    }
    unknown = sorted(k for k in raw.keys() if k not in known)
    for key in unknown:
        report.issues.append(
            MigrationIssue(
                severity="info",
                path=key,
                message=f"Unknown top-level key `{key}`",
                hint="Remove it if unused or move it to a dedicated extension namespace",
                can_autofix=False,
            )
        )
