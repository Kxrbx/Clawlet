"""Hybrid task router — rules first (fast, free), small LLM as fallback.

Classification contract: :func:`classify` never raises and never blocks;
on any doubt it returns ``("chat", low_confidence)`` so the orchestrator
can apply the trivial-fallback path. The optional LLM classifier is
injected as a callable (sync or async) returning a task-kind string —
the router stays testable without network access.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from loguru import logger

# Ordered (kind, patterns). First match wins. English + French keywords.
_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "code",
        (
            r"\bcode\b",
            r"\bdebug\b",
            r"\bbug\b",
            r"\bfunction\b",
            r"\bclass\b",
            r"\brefactor\b",
            r"\brefactoriser\b",
            r"\bcommit\b",
            r"\bmerge\b",
            r"\bpull request\b",
            r"\bpytest\b",
            r"\btraceback\b",
            r"\bstack ?trace\b",
            r"\bcoder\b",
            r"\bprogrammer\b",
            r"\bscript\b",
        ),
    ),
    (
        "plan",
        (
            r"\bplan\b",
            r"\bplanifier\b",
            r"\broadmap\b",
            r"\bfeuille de route\b",
            r"\barchitecture\b",
            r"\bdesign doc\b",
            r"\bproposal\b",
            r"\bproposition\b",
            r"\bstrategy\b",
            r"\bstratégie\b",
        ),
    ),
    (
        "research",
        (
            r"\bresearch\b",
            r"\brecherche\b",
            r"\bcompare\b",
            r"\bcomparer\b",
            r"\bwhat is\b",
            r"\bqu'est-ce\b",
            r"\bexplain\b",
            r"\bexplique\b",
            r"\binvestigate\b",
            r"\benquêter\b",
            r"\banalyze\b",
            r"\banalyse\b",
        ),
    ),
    (
        "browser",
        (
            r"https?://",
            r"\bbrowse\b",
            r"\bnavigate\b",
            r"\bweb ?page\b",
            r"\bscreenshot\b",
            r"\bcrawl\b",
            r"\bscrape\b",
        ),
    ),
    (
        "memory",
        (
            r"\bremember\b",
            r"\bsouviens\b",
            r"\bmemory\b",
            r"\bmémoire\b",
            r"\brecall\b",
            r"\brappelle\b",
            r"\bforget\b",
            r"\boublie\b",
            r"\bnote\b",
            r"\btodo\b",
            r"\bremind\b",
            r"\brappel\b",
        ),
    ),
    (
        "review",
        (
            r"\breview\b",
            r"\brelire\b",
            r"\brelecture\b",
            r"\bproofread\b",
            r"\bcorrige\b",
            r"\bcorrect\b",
            r"\bfeedback\b",
            r"\bretour\b",
        ),
    ),
)

_COMPILED: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (kind, re.compile("|".join(patterns), re.IGNORECASE)) for kind, patterns in _RULES
)

_TRIVIAL_RE = re.compile(
    r"^(hi|hello|hey|salut|bonjour|bonsoir|yo|merci|thanks|thank you|ok|okay|oui|non|yes|no|bye|au revoir)\b[\s!.?]*$",
    re.IGNORECASE,
)

LlmClassifier = Callable[[str], "str | Awaitable[str]"]


@dataclass(slots=True)
class Classification:
    kind: str
    confidence: float  # 0.0 - 1.0
    reason: str
    source: str = "rules"  # rules | llm | fallback


def classify_rules(text: str) -> Classification | None:
    """Rule pass. Returns None when no rule matches."""
    content = (text or "").strip()
    if not content:
        return Classification(
            kind="chat", confidence=0.2, reason="empty input", source="rules"
        )
    if _TRIVIAL_RE.match(content):
        return Classification(
            kind="chat", confidence=0.95, reason="trivial greeting", source="rules"
        )
    for kind, pattern in _COMPILED:
        if pattern.search(content):
            return Classification(
                kind=kind, confidence=0.8, reason=f"rule:{kind}", source="rules"
            )
    return None


async def _maybe_await(value) -> str:
    if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
        return str(await value)
    return str(value)


async def classify(
    text: str,
    *,
    llm_classifier: LlmClassifier | None = None,
    valid_kinds: frozenset[str] | None = None,
) -> Classification:
    """Hybrid classify: rules first, injected LLM classifier on miss.

    Never raises: any LLM error or unknown kind degrades to chat/low.
    """
    hit = classify_rules(text)
    if hit is not None:
        return hit
    if llm_classifier is None:
        return _chat_fallback("no rule matched", "fallback")
    try:
        raw = await _maybe_await(llm_classifier(text))
        kind = raw.strip().lower()
        if valid_kinds is not None and kind not in valid_kinds:
            logger.warning(
                f"LLM classifier returned unknown kind {kind!r}; falling back to chat"
            )
            return _chat_fallback("unknown llm kind", "llm")
        return Classification(
            kind=kind, confidence=0.65, reason="llm classifier", source="llm"
        )
    except Exception as e:
        logger.warning(f"LLM classifier failed ({e}); falling back to chat")
        return _chat_fallback("llm error", "fallback")


def _chat_fallback(reason: str, source: str) -> Classification:
    return Classification(kind="chat", confidence=0.3, reason=reason, source=source)


def is_trivial(text: str, *, max_chars: int = 200) -> bool:
    """Trivial check for the orchestrator direct-fallback path."""
    content = (text or "").strip()
    if not content:
        return True
    if len(content) > max_chars:
        return False
    return bool(_TRIVIAL_RE.match(content))
