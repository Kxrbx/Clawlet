"""Unit tests for HistoryTrimmer budgets (count + chars + tool cap)."""

import logging

from clawlet.agent.history_trimmer import HistoryTrimmer
from clawlet.agent.models import Message


def _trimmer(**kwargs):
    return HistoryTrimmer(max_history=10, logger=logging.getLogger("test"), **kwargs)


def _msgs(n, *, role="user", size=10):
    return [Message(role=role, content=f"m{i} " + "x" * size) for i in range(n)]


def test_noop_when_small():
    history = _msgs(5)
    snapshot = list(history)
    _trimmer().trim(history)
    assert [m.content for m in history] == [m.content for m in snapshot]


def test_char_budget_triggers_trim_below_count_limit():
    history = _msgs(5, size=2000)  # ~10k chars, count fine
    _trimmer(max_chars=5000).trim(history)
    assert len(history) <= 10
    assert history[0].role == "system"
    assert history[0].metadata.get("summary") is True


def test_tool_outputs_capped_metadata_kept():
    history = [
        Message(role="user", content="read it"),
        Message(
            role="tool",
            content="y" * 5000,
            metadata={"tool_call_id": "1", "tool_name": "read_file"},
        ),
    ]
    _trimmer().trim(history)
    tool = next(m for m in history if m.role == "tool")
    assert len(tool.content) < 5000
    assert "truncated" in tool.content
    assert tool.metadata["tool_call_id"] == "1"
    assert history[0].content == "read it"


def test_summary_carried_forward_on_repeated_trims():
    history = _msgs(12, size=50)
    trimmer = _trimmer()
    trimmer.trim(history)
    first_summary = history[0].content
    assert history[0].metadata.get("summary") is True
    history.extend(_msgs(12, size=50))
    trimmer.trim(history)
    assert history[0].metadata.get("summary") is True
    assert len(history) <= 10
    assert first_summary.splitlines()[1] in history[0].content
