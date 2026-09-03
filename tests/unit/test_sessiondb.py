"""Unit tests for SessionDB (P2)."""

import asyncio

import pytest

from clawlet.storage.session_db import SessionRecord, SessionStore
from clawlet.storage.sqlite import SQLiteStorage


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "clawlet.db"


def _init_store(db_path):
    store = SessionStore(db_path)
    _run(store.initialize())
    return store


# -- sessions -------------------------------------------------------------
def test_record_and_get_session(db_path):
    store = _init_store(db_path)
    try:
        _run(
            store.record_session(
                SessionRecord(
                    session_id="s1",
                    parent_session_id="",
                    task_kind="code",
                    profile_snapshot={"provider": "openai"},
                    source="cli",
                )
            )
        )
        rec = _run(store.get_session("s1"))
        assert rec is not None
        assert rec.task_kind == "code"
        assert rec.profile_snapshot == {"provider": "openai"}
        assert rec.source == "cli"
        assert _run(store.get_session("missing")) is None
    finally:
        _run(store.close())


def test_record_session_idempotent_upsert(db_path):
    store = _init_store(db_path)
    try:
        _run(store.record_session(SessionRecord(session_id="s", task_kind="code")))
        _run(store.record_session(SessionRecord(session_id="s", task_kind="plan")))
        assert _run(store.get_session("s")).task_kind == "plan"
    finally:
        _run(store.close())


# -- search -----------------------------------------------------------------
def _seed_messages(db_path):
    storage = SQLiteStorage(db_path)
    _run(storage.initialize())
    try:
        _run(
            storage.store_message(
                "sess-a", "user", "the quick brown fox jumps over deploy key alpha"
            )
        )
        _run(
            storage.store_message(
                "sess-a", "assistant", "acknowledged, nothing about foxes here"
            )
        )
        _run(
            storage.store_message(
                "sess-b", "user", "completely unrelated weather report"
            )
        )
    finally:
        _run(storage.close())


def test_session_search_finds_terms(db_path):
    _seed_messages(db_path)
    store = _init_store(db_path)  # backfills FTS index
    try:
        hits = _run(store.session_search("deploy key"))
        assert any(h["session_id"] == "sess-a" for h in hits)
        assert all(len(h["snippet"]) <= 200 for h in hits)
        scoped = _run(store.session_search("deploy key", session_id="sess-b"))
        assert scoped == []
        assert _run(store.session_search("   ")) == []
        assert _run(store.session_search("zzz-no-such-term-zzz")) == []
    finally:
        _run(store.close())


def test_session_search_like_fallback(db_path):
    _seed_messages(db_path)
    store = _init_store(db_path)
    store._fts_available = False  # force LIKE path
    try:
        hits = _run(store.session_search("weather"))
        assert any(h["session_id"] == "sess-b" for h in hits)
    finally:
        _run(store.close())
