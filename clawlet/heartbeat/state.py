"""Persistent heartbeat state and policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Optional

from loguru import logger

UTC = timezone.utc


def _parse_dt(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _iso(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    return dt.astimezone(UTC).isoformat()


@dataclass
class HeartbeatDecision:
    should_publish: bool
    reason: str
    check_types: list[str]
    due_checks: list[str]
    route: dict[str, str]


class HeartbeatStateStore:
    """Manage long-lived heartbeat state in memory/heartbeat-state.json."""

    CHECK_PATTERNS = {
        "email": (r"\bemail\b", r"\bmail\b", r"\binbox\b", r"\bunread\b"),
        "calendar": (r"\bcalendar\b", r"\bevent\b", r"\bmeeting\b"),
        "notifications": (r"\bnotification", r"\bmention", r"\breply", r"\bdm\b", r"\bmessage\b"),
        "social": (r"\bmoltbook\b", r"\bmolthub\b", r"\btwitter\b", r"\bfarcaster\b", r"\bsocial\b"),
        "weather": (r"\bweather\b", r"\brain\b", r"\btemperature\b"),
        "project": (r"\bproject\b", r"\bgit\b", r"\bdoc", r"\bworkspace\b", r"\brepo"),
        "memory": (r"\bmemory\.md\b", r"\bmemory\b", r"\bjournal\b", r"\breview\b"),
    }
    CHECK_COOLDOWNS = {
        "email": timedelta(hours=2),
        "calendar": timedelta(hours=2),
        "notifications": timedelta(minutes=30),
        "social": timedelta(minutes=30),
        "weather": timedelta(hours=6),
        "project": timedelta(hours=4),
        "memory": timedelta(hours=24),
        "general": timedelta(minutes=30),
    }
    OUTREACH_COOLDOWN = timedelta(hours=8)
    SUCCESS_PREFIXES = ("heartbeat_ok", "heartbeat_action_taken")
    DEGRADED_PREFIXES = ("heartbeat_degraded",)
    BLOCKED_PREFIXES = ("heartbeat_blocked", "heartbeat_needs_attention")

    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return self._default_state()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to load heartbeat state {self.path}: {e}")
            return self._default_state()
        if not isinstance(payload, dict):
            return self._default_state()
        state = self._default_state()
        state.update(payload)
        state["last_checks"] = dict(state.get("last_checks") or {})
        state["last_route"] = dict(state.get("last_route") or {})
        state["last_blockers"] = [str(x) for x in list(state.get("last_blockers") or [])[:5]]
        state["recent_actions"] = [str(x) for x in list(state.get("recent_actions") or [])[:5]]
        return state

    def save(self, state: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
        except Exception as e:
            logger.warning(f"Failed to save heartbeat state {self.path}: {e}")

    def evaluate_tick(
        self,
        *,
        now: datetime,
        context: str,
        route: Optional[dict[str, str]],
        interval_minutes: int,
    ) -> HeartbeatDecision:
        state = self.load()
        check_types = self.infer_check_types(context)
        due_checks = self._due_checks(now, state, check_types, interval_minutes)
        last_outreach = _parse_dt(state.get("last_outreach_at", ""))
        last_result_at = _parse_dt(state.get("last_result_at", ""))
        active_blockers = list(state.get("last_blockers") or [])
        if not route:
            return HeartbeatDecision(False, "no_route", check_types, due_checks, {})
        if due_checks:
            return HeartbeatDecision(True, "checks_due", check_types, due_checks, dict(route))
        if active_blockers and last_result_at is not None and now - last_result_at >= timedelta(minutes=max(1, int(interval_minutes))):
            return HeartbeatDecision(True, "blocker_recheck_due", check_types, due_checks, dict(route))
        if active_blockers and (last_outreach is None or now - last_outreach >= self.OUTREACH_COOLDOWN):
            return HeartbeatDecision(True, "blocker_attention_due", check_types, due_checks, dict(route))
        return HeartbeatDecision(False, "no_due_checks_no_delta", check_types, due_checks, dict(route))

    def record_runner_decision(
        self,
        *,
        now: datetime,
        status: str,
        reason: str,
        route: Optional[dict[str, str]] = None,
        check_types: Optional[list[str]] = None,
        due_checks: Optional[list[str]] = None,
    ) -> None:
        state = self.load()
        state["last_tick_at"] = _iso(now)
        state["last_decision"] = status
        state["last_reason"] = reason
        if route:
            state["last_route"] = dict(route)
        if check_types is not None:
            state["last_planned_checks"] = list(check_types)
        if due_checks is not None:
            state["last_due_checks"] = list(due_checks)
        if status == "published":
            state["last_published_at"] = _iso(now)
        self.save(state)

    def record_cycle_result(
        self,
        *,
        now: datetime,
        response_text: str,
        tool_names: list[str],
        route: Optional[dict[str, str]] = None,
        check_types: Optional[list[str]] = None,
        blockers: Optional[list[str]] = None,
    ) -> None:
        state = self.load()
        text = (response_text or "").strip()
        lowered = text.lower()
        outcome_kind = self._classify_outcome_kind(lowered)
        state["last_result_at"] = _iso(now)
        state["last_result"] = text
        state["last_outcome_kind"] = outcome_kind
        if route:
            state["last_route"] = dict(route)
        checks_completed = outcome_kind in {"ok", "action_taken"}
        if checks_completed:
            if check_types:
                for name in check_types:
                    state.setdefault("last_checks", {})[name] = _iso(now)
            if tool_names:
                for inferred in self.infer_check_types(" ".join(tool_names)):
                    state.setdefault("last_checks", {})[inferred] = _iso(now)
        if blockers:
            state["last_blockers"] = [str(x) for x in blockers[:5]]
        elif outcome_kind == "blocked" or "could not" in lowered or "failed" in lowered:
            state["last_blockers"] = [text[:280]]
        else:
            state["last_blockers"] = []
        if outcome_kind == "ok":
            state["last_heartbeat_ok_at"] = _iso(now)
            state["last_success_at"] = _iso(now)
            state["consecutive_noops"] = int(state.get("consecutive_noops", 0) or 0) + 1
        elif outcome_kind == "action_taken":
            state["last_success_at"] = _iso(now)
            state["last_action_at"] = _iso(now)
            state["consecutive_noops"] = 0
            recent = [self._summarize_action(tool_names, response_text)] + list(state.get("recent_actions") or [])
            state["recent_actions"] = [x for x in recent if x][:5]
        elif outcome_kind == "degraded":
            state["last_degraded_at"] = _iso(now)
            state["consecutive_noops"] = 0
        else:
            state["consecutive_noops"] = 0
        if outcome_kind == "blocked":
            state["last_blocked_at"] = _iso(now)
            state["last_attention_at"] = _iso(now)
        elif outcome_kind == "degraded":
            state["last_attention_at"] = _iso(now)
        self.save(state)

    def record_outreach(self, *, now: datetime, response_text: str) -> None:
        state = self.load()
        state["last_outreach_at"] = _iso(now)
        state["last_outreach_preview"] = (response_text or "").strip()[:280]
        self.save(state)

    def build_prompt_summary(self, now: Optional[datetime] = None) -> str:
        now = now or datetime.now(UTC)
        state = self.load()
        lines = ["Heartbeat State"]
        planned = ", ".join(state.get("last_planned_checks") or []) or "none"
        due = ", ".join(state.get("last_due_checks") or []) or "none"
        lines.append(f"- Planned checks: {planned}")
        lines.append(f"- Due checks: {due}")
        for key in ("notifications", "social", "email", "calendar", "project", "memory", "weather", "general"):
            last_value = _parse_dt((state.get("last_checks") or {}).get(key, ""))
            if last_value is None:
                continue
            age_minutes = int((now - last_value).total_seconds() // 60)
            lines.append(f"- Last {key} check: {age_minutes}m ago")
        if state.get("last_attention_at"):
            lines.append(f"- Last attention alert: {state['last_attention_at']}")
        if state.get("last_degraded_at"):
            lines.append(f"- Last degraded run: {state['last_degraded_at']}")
        if state.get("last_outreach_at"):
            lines.append(f"- Last outreach: {state['last_outreach_at']}")
        if state.get("recent_actions"):
            lines.append(f"- Recent action: {state['recent_actions'][0]}")
        if state.get("last_blockers"):
            lines.append(f"- Active blocker: {state['last_blockers'][0][:180]}")
        lines.append("- If no due checks and no urgent blocker, prefer HEARTBEAT_OK.")
        return "\n".join(lines)

    @classmethod
    def infer_check_types(cls, context: str) -> list[str]:
        text = (context or "").strip().lower()
        inferred: list[str] = []
        for check_type, patterns in cls.CHECK_PATTERNS.items():
            if any(re.search(pattern, text) for pattern in patterns):
                inferred.append(check_type)
        if not inferred and text:
            inferred.append("general")
        return inferred

    def _due_checks(self, now: datetime, state: dict, check_types: list[str], interval_minutes: int) -> list[str]:
        due: list[str] = []
        last_checks = dict(state.get("last_checks") or {})
        for check_type in check_types:
            last_dt = _parse_dt(last_checks.get(check_type, ""))
            cooldown = self.CHECK_COOLDOWNS.get(
                check_type,
                timedelta(minutes=max(10, int(interval_minutes))),
            )
            if last_dt is None or now - last_dt >= cooldown:
                due.append(check_type)
        return due

    @staticmethod
    def _default_state() -> dict:
        return {
            "version": 1,
            "last_tick_at": "",
            "last_decision": "",
            "last_reason": "",
            "last_route": {},
            "last_published_at": "",
            "last_result_at": "",
            "last_result": "",
            "last_outcome_kind": "",
            "last_heartbeat_ok_at": "",
            "last_success_at": "",
            "last_blocked_at": "",
            "last_degraded_at": "",
            "last_attention_at": "",
            "last_action_at": "",
            "last_outreach_at": "",
            "last_outreach_preview": "",
            "last_planned_checks": [],
            "last_due_checks": [],
            "last_checks": {},
            "last_blockers": [],
            "recent_actions": [],
            "consecutive_noops": 0,
        }

    @classmethod
    def _classify_outcome_kind(cls, lowered: str) -> str:
        if lowered.startswith(cls.BLOCKED_PREFIXES):
            return "blocked"
        if lowered.startswith(cls.DEGRADED_PREFIXES):
            return "degraded"
        if lowered.startswith("heartbeat_action_taken"):
            return "action_taken"
        if lowered.startswith("heartbeat_ok"):
            return "ok"
        return "other"

    @staticmethod
    def _summarize_action(tool_names: list[str], response_text: str) -> str:
        tools = ", ".join(tool_names[:3])
        text = (response_text or "").strip().splitlines()[0][:160]
        if tools and text:
            return f"{tools}: {text}"
        return tools or text
