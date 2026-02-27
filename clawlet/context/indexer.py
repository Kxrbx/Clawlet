"""Incremental repository indexer for context retrieval."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from clawlet.context.models import IndexedFile

SUPPORTED_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".sh",
}

IGNORE_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

MAX_FILE_SIZE = 300_000
MAX_PREVIEW_CHARS = 4000

_PY_SYMBOL_RE = re.compile(r"^\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
_GENERIC_SYMBOL_RE = re.compile(
    r"^\s*(?:function|class|interface|type|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


class RepositoryIndexer:
    """Builds and persists an incremental file/symbol index."""

    def __init__(self, workspace: Path, cache_dir: Path):
        self.workspace = workspace
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "context_index.json"

    def build_index(self) -> tuple[str, dict[str, IndexedFile]]:
        """Build or refresh the repository index and return repo hash + files."""
        previous = self._load_index()
        previous_files = previous.get("files") or {}

        indexed: dict[str, IndexedFile] = {}
        repo_parts: list[str] = []

        for path in self._iter_candidate_files():
            rel = path.relative_to(self.workspace).as_posix()
            try:
                stat = path.stat()
            except OSError:
                continue

            mtime_ns = int(stat.st_mtime_ns)
            size = int(stat.st_size)
            repo_parts.append(f"{rel}:{mtime_ns}:{size}")

            prev = previous_files.get(rel)
            if (
                isinstance(prev, dict)
                and prev.get("mtime_ns") == mtime_ns
                and prev.get("size") == size
            ):
                indexed[rel] = IndexedFile(
                    path=rel,
                    mtime_ns=mtime_ns,
                    size=size,
                    symbols=list(prev.get("symbols") or []),
                    preview=str(prev.get("preview") or ""),
                )
                continue

            text = self._read_text(path)
            symbols = self._extract_symbols(path.suffix.lower(), text)
            preview = text[:MAX_PREVIEW_CHARS]
            indexed[rel] = IndexedFile(
                path=rel,
                mtime_ns=mtime_ns,
                size=size,
                symbols=symbols,
                preview=preview,
            )

        repo_hash = hashlib.sha256("|".join(sorted(repo_parts)).encode("utf-8")).hexdigest()
        self._save_index(repo_hash, indexed)
        return repo_hash, indexed

    def _iter_candidate_files(self):
        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            if any(part in IGNORE_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                if path.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            yield path

    def _extract_symbols(self, suffix: str, text: str) -> list[str]:
        if not text:
            return []
        matches = _PY_SYMBOL_RE.findall(text) if suffix == ".py" else _GENERIC_SYMBOL_RE.findall(text)
        seen = set()
        out = []
        for item in matches:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
            if len(out) >= 80:
                break
        return out

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _load_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_index(self, repo_hash: str, indexed: dict[str, IndexedFile]) -> None:
        payload = {
            "repo_hash": repo_hash,
            "files": {k: asdict(v) for k, v in indexed.items()},
        }
        self.index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
