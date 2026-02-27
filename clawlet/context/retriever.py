"""Query-time retrieval and context packing."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict
from pathlib import Path

from clawlet.context.models import ContextPack, ContextSnippet, IndexedFile

_TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_\-]{1,}")


class QueryContextCache:
    """Small disk-backed cache for query packs keyed by repo hash + query fingerprint."""

    def __init__(self, cache_path: Path, max_entries: int = 200):
        self.cache_path = cache_path
        self.max_entries = max_entries
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> dict | None:
        data = self._load()
        entry = data.get(key)
        if not entry:
            return None
        entry["last_access"] = time.time()
        data[key] = entry
        self._save(data)
        return entry

    def put(self, key: str, payload: dict) -> None:
        data = self._load()
        payload["last_access"] = time.time()
        data[key] = payload
        if len(data) > self.max_entries:
            victims = sorted(data.items(), key=lambda kv: kv[1].get("last_access", 0.0))
            for victim, _ in victims[: len(data) - self.max_entries]:
                data.pop(victim, None)
        self._save(data)

    def _load(self) -> dict:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict) -> None:
        self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def query_fingerprint(query: str) -> str:
    normalized = " ".join(tokenize(query))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def tokenize(value: str) -> list[str]:
    seen = set()
    out: list[str] = []
    for tok in _TOKEN_RE.findall((value or "").lower()):
        if len(tok) < 3:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def retrieve_context(
    repo_hash: str,
    query: str,
    files: dict[str, IndexedFile],
    max_files: int = 5,
    char_budget: int = 3500,
) -> ContextPack:
    """Retrieve top snippets for query against indexed files."""
    query_tokens = tokenize(query)
    fp = query_fingerprint(query)

    if not query_tokens:
        return ContextPack(repo_hash=repo_hash, query_fingerprint=fp, snippets=[])

    scored: list[tuple[float, IndexedFile, str]] = []
    for item in files.values():
        score, reason = _score_file(query_tokens, item)
        if score <= 0:
            continue
        scored.append((score, item, reason))

    scored.sort(key=lambda x: x[0], reverse=True)

    snippets: list[ContextSnippet] = []
    used_chars = 0
    for score, item, reason in scored[:max_files]:
        excerpt = _excerpt_for(item, query_tokens, max_chars=min(1200, char_budget))
        if not excerpt:
            continue
        if used_chars + len(excerpt) > char_budget:
            continue
        snippets.append(ContextSnippet(path=item.path, excerpt=excerpt, score=score, reason=reason))
        used_chars += len(excerpt)

    return ContextPack(repo_hash=repo_hash, query_fingerprint=fp, snippets=snippets)


def serialize_pack(pack: ContextPack) -> dict:
    data = {
        "repo_hash": pack.repo_hash,
        "query_fingerprint": pack.query_fingerprint,
        "cache_hit": pack.cache_hit,
        "snippets": [asdict(s) for s in pack.snippets],
    }
    return data


def deserialize_pack(data: dict) -> ContextPack:
    snippets = [ContextSnippet(**item) for item in (data.get("snippets") or [])]
    return ContextPack(
        repo_hash=str(data.get("repo_hash") or ""),
        query_fingerprint=str(data.get("query_fingerprint") or ""),
        snippets=snippets,
        cache_hit=bool(data.get("cache_hit", False)),
    )


def _score_file(query_tokens: list[str], item: IndexedFile) -> tuple[float, str]:
    score = 0.0
    reason_parts: list[str] = []

    path_tokens = set(tokenize(item.path))
    symbol_tokens = set(tokenize(" ".join(item.symbols)))
    preview_tokens = set(tokenize(item.preview[:1200]))

    path_overlap = len(path_tokens.intersection(query_tokens))
    symbol_overlap = len(symbol_tokens.intersection(query_tokens))
    preview_overlap = len(preview_tokens.intersection(query_tokens))

    if path_overlap:
        score += path_overlap * 4.0
        reason_parts.append(f"path:{path_overlap}")
    if symbol_overlap:
        score += symbol_overlap * 3.0
        reason_parts.append(f"symbols:{symbol_overlap}")
    if preview_overlap:
        score += preview_overlap * 1.5
        reason_parts.append(f"content:{preview_overlap}")

    return score, ",".join(reason_parts)


def _excerpt_for(item: IndexedFile, query_tokens: list[str], max_chars: int = 1000) -> str:
    lines = item.preview.splitlines()
    if not lines:
        return ""

    best_line = 0
    best_score = -1
    for i, line in enumerate(lines):
        line_tokens = set(tokenize(line))
        score = len(line_tokens.intersection(query_tokens))
        if score > best_score:
            best_score = score
            best_line = i

    start = max(0, best_line - 6)
    end = min(len(lines), best_line + 14)
    excerpt = "\n".join(lines[start:end])
    return excerpt[:max_chars]
