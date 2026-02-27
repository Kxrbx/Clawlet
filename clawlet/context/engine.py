"""High-level Context Engine v2 for coding tasks."""

from __future__ import annotations

from pathlib import Path

from clawlet.context.indexer import RepositoryIndexer
from clawlet.context.models import ContextPack
from clawlet.context.retriever import (
    QueryContextCache,
    deserialize_pack,
    query_fingerprint,
    retrieve_context,
    serialize_pack,
)


class ContextEngine:
    """Incremental repo index + cached query retrieval for prompt context."""

    def __init__(self, workspace: Path, cache_dir: Path):
        self.workspace = workspace
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.indexer = RepositoryIndexer(workspace=workspace, cache_dir=self.cache_dir)
        self.query_cache = QueryContextCache(self.cache_dir / "query_cache.json")

    def get_pack(self, query: str, max_files: int = 5, char_budget: int = 3500) -> ContextPack:
        repo_hash, files = self.indexer.build_index()
        qfp = query_fingerprint(query)
        key = f"{repo_hash}:{qfp}:{max_files}:{char_budget}"

        cached = self.query_cache.get(key)
        if cached:
            pack = deserialize_pack(cached)
            pack.cache_hit = True
            return pack

        pack = retrieve_context(
            repo_hash=repo_hash,
            query=query,
            files=files,
            max_files=max_files,
            char_budget=char_budget,
        )
        self.query_cache.put(key, serialize_pack(pack))
        return pack

    def render_for_prompt(self, query: str, max_files: int = 5, char_budget: int = 3500) -> str:
        """Render snippets into a concise system-context block."""
        pack = self.get_pack(query=query, max_files=max_files, char_budget=char_budget)
        if not pack.snippets:
            return ""

        lines = [
            "Repository Context (auto-selected):",
            f"repo_hash={pack.repo_hash[:12]} cache_hit={str(pack.cache_hit).lower()}",
        ]
        for snippet in pack.snippets:
            lines.append(f"\n[file] {snippet.path}  score={snippet.score:.2f}  reason={snippet.reason}")
            lines.append(snippet.excerpt)

        return "\n".join(lines)
