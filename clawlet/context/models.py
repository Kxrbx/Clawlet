"""Typed models for repository context indexing and retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IndexedFile:
    """Indexed representation of a repository file."""

    path: str
    mtime_ns: int
    size: int
    symbols: list[str] = field(default_factory=list)
    preview: str = ""


@dataclass(slots=True)
class ContextSnippet:
    """One retrieved repository snippet."""

    path: str
    excerpt: str
    score: float
    reason: str


@dataclass(slots=True)
class ContextPack:
    """Retrieved context bundle for one query."""

    repo_hash: str
    query_fingerprint: str
    snippets: list[ContextSnippet] = field(default_factory=list)
    cache_hit: bool = False
