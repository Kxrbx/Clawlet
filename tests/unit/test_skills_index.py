"""Tests for the progressive-disclosure skills index (P4)."""

from dataclasses import dataclass

from clawlet.skills.index import (
    INDEX_TOKEN_BUDGET,
    build_skills_index,
    estimate_tokens,
)


@dataclass
class FakeSkill:
    name: str
    description: str = ""
    triggers: tuple = ()


def test_build_index_skips_nameless():
    idx = build_skills_index(
        [FakeSkill(name=""), FakeSkill(name="deploy", description="Ship it")]
    )
    assert [e.name for e in idx.entries] == ["deploy"]


def test_render_is_compact_and_truncates():
    idx = build_skills_index(
        [
            FakeSkill(name="a", description="x" * 500),
            FakeSkill(name="b", description="short"),
        ]
    )
    rendered = idx.render()
    assert "- a: " in rendered and "- b: short" in rendered
    assert "…" in rendered
    assert idx.estimated_tokens <= INDEX_TOKEN_BUDGET


def test_match_ranks_by_keyword_overlap():
    idx = build_skills_index(
        [
            FakeSkill(
                name="deploy", description="ship to production", triggers=("release",)
            ),
            FakeSkill(name="notes", description="take meeting notes"),
        ]
    )
    hits = idx.match("how do I release to production?")
    assert hits and hits[0].name == "deploy"
    assert idx.match("xyzzy-nope-qwerty") == []
    assert idx.match("") == []


def test_index_budget_guard_caps_entries():
    many = [FakeSkill(name=f"s{i:03d}", description="d" * 100) for i in range(500)]
    idx = build_skills_index(many)
    assert idx.estimated_tokens <= INDEX_TOKEN_BUDGET
    assert len(idx.entries) < 500


def test_estimate_tokens_floor():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 400) == 100
