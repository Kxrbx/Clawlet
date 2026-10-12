"""Progressive-disclosure skills index.

Loading every skill into every prompt bloats context linearly. Instead the
stable prompt tier carries only a compact index — one ``name: description``
line per skill (~630 tokens for 50 skills) — and full skill content is
fetched on demand via ``skill_view`` when the router matches.

This module is registry-agnostic: it works over any objects exposing
``name``/``description`` (and optionally ``triggers``), so it stays
unit-testable without a workspace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INDEX_LINE_MAX_CHARS = 120
INDEX_TOKEN_BUDGET = 2000  # ~500 chars/skill safety cap for the prompt tier


@dataclass(slots=True)
class SkillIndexEntry:
    name: str
    description: str
    triggers: tuple[str, ...] = ()
    estimated_tokens: int = 0


@dataclass(slots=True)
class SkillIndex:
    entries: list[SkillIndexEntry] = field(default_factory=list)

    @property
    def estimated_tokens(self) -> int:
        return sum(e.estimated_tokens for e in self.entries)

    def render(self, *, max_chars_per_line: int = INDEX_LINE_MAX_CHARS) -> str:
        """Render the compact index block for the stable prompt tier."""
        lines = []
        for entry in self.entries:
            desc = re.sub(r"\s+", " ", entry.description).strip()
            if len(desc) > max_chars_per_line:
                desc = desc[: max_chars_per_line - 1] + "…"
            lines.append(f"- {entry.name}: {desc}")
        return "\n".join(lines)

    def match(self, query: str, *, top_n: int = 3) -> list[SkillIndexEntry]:
        """Rank entries by keyword overlap with the query (no LLM needed)."""
        tokens = {
            t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query or "") if len(t) > 2
        }
        if not tokens:
            return []
        scored: list[tuple[int, SkillIndexEntry]] = []
        for entry in self.entries:
            haystack = (
                f"{entry.name} {entry.description} {' '.join(entry.triggers)}".lower()
            )
            score = sum(1 for tok in tokens if tok in haystack)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:top_n]]


def estimate_tokens(text: str) -> int:
    """Rough token estimate (chars // 4) for budget checks."""
    return max(1, len(text) // 4)


def build_skills_index(skills) -> SkillIndex:
    """Build an index from skill-like objects (``.name``/``.description``)."""
    entries: list[SkillIndexEntry] = []
    total = 0
    for skill in skills:
        name = str(getattr(skill, "name", "") or "").strip()
        if not name:
            continue
        description = str(getattr(skill, "description", "") or "").strip()
        triggers = getattr(skill, "triggers", None) or ()
        try:
            triggers = tuple(str(t) for t in triggers)
        except TypeError:
            triggers = ()
        line = f"- {name}: {description}"
        tokens = estimate_tokens(line)
        if total + tokens > INDEX_TOKEN_BUDGET:
            break  # budget guard: index must stay cheap
        total += tokens
        entries.append(
            SkillIndexEntry(
                name=name,
                description=description,
                triggers=triggers,
                estimated_tokens=tokens,
            )
        )
    return SkillIndex(entries=entries)
