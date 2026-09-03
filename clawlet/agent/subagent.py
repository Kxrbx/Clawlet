"""Sub-agent spawning — fresh loops with isolated budgets and toolsets.

A sub-agent is a *process, not a thread*: separate provider/model,
separate iteration/tool-call caps, separate tool view, separate session
(with ``parent_session_id`` lineage for SessionDB), and a clean history
containing only the delegated instruction plus a bounded context slice.
Children never re-delegate (``depth >= max_depth`` guard).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clawlet.agent.task_profiles import ResolvedProfile
from clawlet.tools.toolsets import filter_tool_names


@dataclass(slots=True)
class SubagentSpec:
    """Everything needed to spawn one child worker."""

    kind: str
    instruction: str
    context_slice: str = ""
    session_id: str = ""
    parent_session_id: str = ""
    parent_run_id: str = ""
    depth: int = 0
    profile: Any = None  # ResolvedProfile (Any to avoid import weight)


def build_instruction(user_message: str, *, kind: str) -> str:
    """Wrap the user request as a scoped child instruction."""
    return (
        f"[Delegated task | kind={kind}]\n"
        f"{user_message.strip()}\n"
        "Scope: complete only this task. Do not start unrelated work. "
        "Return a concise summary of what was done plus any concrete blocker."
    )


def collect_context_slice(history: list, *, max_chars: int = 2000) -> str:
    """Extract a bounded tail of recent history as plain text context.

    Accepts :class:`Message` objects or plain dicts; newest last, truncated
    from the front to ``max_chars``.
    """
    parts: list[str] = []
    for msg in history[-8:]:
        role = getattr(msg, "role", None) or (
            msg.get("role") if isinstance(msg, dict) else "?"
        )
        content = getattr(msg, "content", None) or (
            msg.get("content") if isinstance(msg, dict) else ""
        )
        if role in ("system", "tool"):
            continue
        text = str(content or "").strip()
        if text:
            parts.append(f"{role}: {text[:500]}")
    joined = "\n".join(parts)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]
    return joined


def spawn_child_loop(
    parent_loop: Any,
    spec: SubagentSpec,
    profile: ResolvedProfile,
):
    """Build a child ``AgentLoop`` sharing identity/workspace but isolated otherwise.

    - Fresh tool registry holding references to the parent's tools, filtered
      by the profile toolset (zero loop changes required).
    - Own provider built from the profile (falls back to the parent's on
      construction error when a fallback is configured).
    - Own budget, model, iteration caps; same memory manager + storage.
    Lazy import of ``AgentLoop`` avoids the ``agent.loop <-> subagent``
    import cycle.
    """
    from clawlet.agent.loop import AgentLoop
    from clawlet.agent.provider_factory import build_provider
    from clawlet.tools.registry import ToolRegistry
    from clawlet.tools.toolsets import normalize_toolsets

    full_config = getattr(parent_loop, "full_config", None) or getattr(
        parent_loop, "config", None
    )
    provider_config = (
        getattr(full_config, "provider", None) if full_config is not None else None
    )
    if provider_config is None:
        provider_config = {}
    try:
        provider = build_provider(
            profile.provider,
            provider_config,
            model=profile.model,
        )
    except Exception:
        if profile.fallback_provider:
            provider = build_provider(
                profile.fallback_provider,
                provider_config,
                model=profile.fallback_model,
            )
        else:
            raise

    toolsets = normalize_toolsets(profile.toolset)
    child_registry = ToolRegistry()
    parent_tools = parent_loop.tools
    for tool in parent_tools.all_tools():
        if filter_tool_names([tool.name], toolsets):
            child_registry.register(tool)
    for alias, canonical in parent_tools.get_aliases().items():
        if filter_tool_names([canonical], toolsets):
            child_registry.register_alias(alias, canonical)

    child = AgentLoop(
        bus=parent_loop.bus,
        workspace=parent_loop.workspace,
        identity=parent_loop.identity,
        provider=provider,
        tools=child_registry,
        memory_manager=parent_loop.memory,
        model=profile.model or provider.get_default_model(),
        max_iterations=profile.max_iterations,
        max_tool_calls_per_message=profile.tool_call_limit,
        storage_config=getattr(parent_loop, "storage_config", None),
        runtime_config=getattr(parent_loop, "runtime_config", None),
    )
    # Lineage for SessionDB / replay (consumed in Phase 2, stored meanwhile).
    child._parent_session_id = spec.parent_session_id
    child._task_kind = spec.kind
    child._delegation_depth = spec.depth + 1
    return child


def is_delegation_allowed(depth: int, max_depth: int = 1) -> bool:
    """Depth guard: children at max depth must not re-delegate."""
    return depth < max_depth
