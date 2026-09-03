"""Per-task execution profiles — user-configurable provider/model per task kind.

Fixed taxonomy (overridable defaults)::

    code, plan, research, browser, memory, review, ops-tool, chat, scheduled

Each kind resolves to a :class:`TaskProfile` via inheritance chain::

    task_profiles[kind] -> task_profiles.defaults -> global provider.primary

A profile carries the full execution contract (provider, model, toolset,
budgets, timeout, temperature, fallback), not just provider+model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TASK_KINDS: tuple[str, ...] = (
    "code",
    "plan",
    "research",
    "browser",
    "memory",
    "review",
    "ops-tool",
    "chat",
    "scheduled",
)

DEFAULT_TOOLSET_BY_KIND: dict[str, str] = {
    "code": "coding",
    "plan": "minimal",
    "research": "browser",
    "browser": "browser",
    "memory": "memory-only",
    "review": "minimal",
    "ops-tool": "full",
    "chat": "minimal",
    "scheduled": "full",
}

DEFAULT_BUDGET_BY_KIND: dict[str, dict[str, int]] = {
    "code": {"max_iterations": 50, "tool_call_limit": 20},
    "plan": {"max_iterations": 15, "tool_call_limit": 8},
    "research": {"max_iterations": 25, "tool_call_limit": 15},
    "browser": {"max_iterations": 20, "tool_call_limit": 12},
    "memory": {"max_iterations": 10, "tool_call_limit": 6},
    "review": {"max_iterations": 10, "tool_call_limit": 6},
    "ops-tool": {"max_iterations": 15, "tool_call_limit": 10},
    "chat": {"max_iterations": 5, "tool_call_limit": 4},
    "scheduled": {"max_iterations": 20, "tool_call_limit": 10},
}


class TaskProfileFallback(BaseModel):
    """Fallback provider used when the primary profile provider fails."""

    provider: str = "ollama"
    model: str = ""


class TaskProfile(BaseModel):
    """Full execution contract for one task kind. Empty fields inherit."""

    provider: str = ""
    model: str = ""
    toolset: str = ""
    max_iterations: int = Field(default=0, ge=0, le=100)
    tool_call_limit: int = Field(default=0, ge=0, le=100)
    timeout_s: float = Field(default=0, ge=0, le=3600)
    temperature: float = Field(default=-1, ge=-1, le=2)
    fallback: TaskProfileFallback | None = None


class OrchestratorSettings(BaseModel):
    """Orchestrator behavior (always-delegate with direct fallback)."""

    model_provider: str = ""
    model: str = ""
    max_iterations: int = Field(default=5, ge=1, le=20)
    allow_direct_fallback: bool = True
    trivial_max_chars: int = Field(default=200, ge=1, le=2000)
    classifier_mode: Literal["rules", "llm", "hybrid"] = "hybrid"
    classifier_timeout_s: float = Field(default=5.0, ge=1.0, le=60.0)
    max_depth: int = Field(default=1, ge=0, le=3)


def default_profiles() -> dict[str, TaskProfile]:
    """Build default profiles for every known task kind.

    Kind entries intentionally carry only the toolset — budgets, timeout
    and temperature resolve from the ``DEFAULT_*`` constants so a sparse
    user ``profiles[kind]`` (or no entry at all) never gets shadowed by
    fully-populated built-ins. Explicit user fields always win via
    ``model_fields_set`` (see :func:`resolve_profile`).
    """
    profiles: dict[str, TaskProfile] = {}
    for kind in TASK_KINDS:
        profiles[kind] = TaskProfile(toolset=DEFAULT_TOOLSET_BY_KIND[kind])
    profiles["defaults"] = TaskProfile(
        fallback=TaskProfileFallback(provider="ollama", model="llama3.2"),
    )
    return profiles


class ResolvedProfile:
    """A task profile with all inheritance applied (plain data)."""

    def __init__(
        self,
        *,
        kind: str,
        provider: str,
        model: str,
        toolset: str,
        max_iterations: int,
        tool_call_limit: int,
        timeout_s: float,
        temperature: float,
        fallback_provider: str = "",
        fallback_model: str = "",
    ):
        self.kind = kind
        self.provider = provider
        self.model = model
        self.toolset = toolset
        self.max_iterations = max_iterations
        self.tool_call_limit = tool_call_limit
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.fallback_provider = fallback_provider
        self.fallback_model = fallback_model

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "provider": self.provider,
            "model": self.model,
            "toolset": self.toolset,
            "max_iterations": self.max_iterations,
            "tool_call_limit": self.tool_call_limit,
            "timeout_s": self.timeout_s,
            "temperature": self.temperature,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
        }


def _non_empty(value: str) -> bool:
    return bool(value and str(value).strip())


def resolve_profile(
    kind: str,
    profiles: dict[str, TaskProfile] | None,
    *,
    global_provider: str = "openrouter",
    global_model: str = "",
) -> ResolvedProfile:
    """Resolve a task kind to an executable profile.

    Precedence per field: ``profiles[kind]`` -> explicit user
    ``profiles["defaults"]`` -> kind built-in default -> global primary.
    "Explicit" means present in the passed dict *and* set to a non-empty
    value via ``model_fields_set`` (so the sparse built-in ``defaults``
    entry — fallback only — never shadows kind built-ins). Unknown kinds
    fall back to ``defaults``. Never raises.
    """
    profiles = profiles or {}
    specific = profiles.get(kind)
    user_defaults = profiles.get("defaults")
    budget = DEFAULT_BUDGET_BY_KIND.get(
        kind, {"max_iterations": 20, "tool_call_limit": 10}
    )

    def _str(*candidates: str, fallback: str = "") -> str:
        for cand in candidates:
            if _non_empty(cand):
                return cand.strip()
        return fallback

    def _explicit(profile: TaskProfile | None, fname: str) -> bool:
        return (
            profile is not None
            and fname in profile.model_fields_set
            and bool(getattr(profile, fname))
        )

    def _num(fname: str, kind_default: float) -> float:
        if specific is not None and fname in specific.model_fields_set:
            val = getattr(specific, fname)
            if isinstance(val, bool):
                pass
            elif val:
                return val
        if _explicit(user_defaults, fname):
            return getattr(user_defaults, fname)
        return kind_default

    def _temp() -> float:
        for profile in (specific, user_defaults):
            if (
                profile is not None
                and "temperature" in profile.model_fields_set
                and profile.temperature >= 0
            ):
                return profile.temperature
        return 0.3

    specific_provider = specific.provider if specific else ""
    defaults_provider = user_defaults.provider if user_defaults else ""
    specific_model = specific.model if specific else ""
    defaults_model = user_defaults.model if user_defaults else ""
    specific_toolset = specific.toolset if specific else ""
    defaults_toolset = user_defaults.toolset if user_defaults else ""

    provider = _str(specific_provider, defaults_provider, fallback=global_provider)
    model = _str(specific_model, defaults_model, fallback=global_model)
    toolset = _str(
        specific_toolset,
        defaults_toolset,
        fallback=DEFAULT_TOOLSET_BY_KIND.get(kind, "full"),
    )
    max_iterations = int(_num("max_iterations", budget["max_iterations"]))
    tool_call_limit = int(_num("tool_call_limit", budget["tool_call_limit"]))
    timeout_s = float(_num("timeout_s", 180.0))
    temperature = _temp()
    fallback = (specific.fallback if specific else None) or (
        user_defaults.fallback if user_defaults else None
    )
    return ResolvedProfile(
        kind=kind,
        provider=provider,
        model=model,
        toolset=toolset,
        max_iterations=max_iterations,
        tool_call_limit=tool_call_limit,
        timeout_s=timeout_s,
        temperature=temperature,
        fallback_provider=(fallback.provider if fallback else ""),
        fallback_model=(fallback.model if fallback else ""),
    )
