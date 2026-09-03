"""Named tool bundles (toolsets) — Hermes-style filtering of the tool registry.

A toolset is a named filter over registered tool names. Launching with
``--toolsets coding,browser`` loads different *views* of the same registry,
not different code.
"""

from __future__ import annotations

from collections.abc import Iterable

# Explicit tool names (stable contract). Unknown future tools fall through
# to "full" only — every other toolset is allowlist-based.
_READ_ONLY_TOOLS = frozenset(
    {
        "read_file",
        "list_dir",
        "fetch_url",
        "web_search",
        "search_web",  # alias, kept for coverage
        "recall",
        "search_memory",
        "recent_memories",
        "memory_status",
        "review_daily_notes",
        "list_skills",
        "notes_list_notes",
        "notes_get_note",
    }
)

_CODING_EXTRA = frozenset(
    {
        "write_file",
        "edit_file",
        "apply_patch",
        "shell",
        "http_request",
        "notes_create_note",
        "notes_update_note",
    }
)

_BROWSER_EXTRA = frozenset(
    {
        "fetch_url",
        "web_search",
        "http_request",
    }
)

_MEMORY_TOOLS = frozenset(
    {
        "remember",
        "recall",
        "search_memory",
        "recent_memories",
        "review_daily_notes",
        "curate_memory",
        "memory_status",
    }
)

TOOLSETS: dict[str, frozenset[str] | None] = {
    # None = allow all (full)
    "full": None,
    "minimal": _READ_ONLY_TOOLS,
    "coding": _READ_ONLY_TOOLS | _CODING_EXTRA | frozenset({"install_skill"}),
    "browser": _BROWSER_EXTRA,
    "memory-only": _MEMORY_TOOLS,
}


def normalize_toolsets(raw: Iterable[str] | str | None) -> list[str]:
    """Normalize user input (\"coding,browser\" or [\"coding\"]) to a list of known toolset names."""
    if raw is None:
        return ["full"]
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.split(",")]
    else:
        parts = [str(p).strip().lower() for p in raw]
    names = [p for p in parts if p]
    unknown = [n for n in names if n not in TOOLSETS]
    if unknown:
        raise ValueError(
            f"Unknown toolset(s): {', '.join(unknown)}. Known: {', '.join(sorted(TOOLSETS))}"
        )
    return names or ["full"]


def tool_allowed_in_sets(tool_name: str, sets: Iterable[str]) -> bool:
    """Return True if a tool name is visible in any of the given toolsets."""
    for s in sets:
        allowed = TOOLSETS[s]
        if allowed is None:
            return True
        if tool_name in allowed:
            return True
    return False


def filter_tool_names(names: Iterable[str], sets: Iterable[str]) -> list[str]:
    """Filter an iterable of tool names to those visible in the given toolsets."""
    set_list = list(sets)
    return [n for n in names if tool_allowed_in_sets(n, set_list)]
