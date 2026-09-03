"""Unit tests for the v2 always-on orchestrator (no network)."""

import asyncio
from dataclasses import dataclass, field

import pytest

from clawlet.agent import task_router
from clawlet.agent.orchestrator import Orchestrator
from clawlet.agent.subagent import (
    build_instruction,
    collect_context_slice,
    is_delegation_allowed,
)
from clawlet.agent.task_profiles import (
    OrchestratorSettings,
    TaskProfile,
    default_profiles,
    resolve_profile,
)
from clawlet.tools.toolsets import filter_tool_names, normalize_toolsets


# -- profiles -----------------------------------------------------------
def test_resolve_profile_inherits_defaults_and_global():
    profiles = default_profiles()
    profiles["code"] = TaskProfile(provider="anthropic", model="claude-x")
    resolved = resolve_profile("code", profiles, global_provider="openrouter")
    assert resolved.provider == "anthropic"
    assert resolved.model == "claude-x"
    assert resolved.toolset == "coding"  # kind default preserved
    assert resolved.max_iterations == 50


def test_resolve_unknown_kind_falls_back_to_defaults():
    resolved = resolve_profile("nope", {}, global_provider="openrouter")
    assert resolved.provider == "openrouter"
    assert resolved.toolset == "full"


def test_resolve_explicit_overrides_win():
    profiles = default_profiles()
    profiles["defaults"] = TaskProfile(
        provider="openai",
        model="g-x",
        toolset="minimal",
        max_iterations=7,
        tool_call_limit=3,
        timeout_s=60.0,
        temperature=0.1,
    )
    resolved = resolve_profile("chat", profiles, global_provider="openrouter")
    assert (resolved.provider, resolved.model) == ("openai", "g-x")
    assert resolved.max_iterations == 7


# -- router --------------------------------------------------------------
def test_router_rules_code_and_memory():
    assert task_router.classify_rules("fix this bug in foo.py").kind == "code"
    assert task_router.classify_rules("remember my deploy key").kind == "memory"
    assert task_router.classify_rules("https://example.com/page").kind == "browser"


def test_router_trivial_greeting():
    hit = task_router.classify_rules("salut")
    assert hit.kind == "chat" and hit.confidence > 0.9
    assert task_router.is_trivial("bonjour")
    assert not task_router.is_trivial("bonjour, debug this traceback please " * 20)


def test_router_llm_fallback_and_unknown_kind():
    async def go():
        ok = await task_router.classify(
            "some vague thing with no keywords xyzzy",
            llm_classifier=lambda text: "research",
            valid_kinds=frozenset({"research", "chat"}),
        )
        assert ok.kind == "research" and ok.source == "llm"
        bad = await task_router.classify(
            "some vague thing xyzzy",
            llm_classifier=lambda text: "nonsense",
            valid_kinds=frozenset({"research", "chat"}),
        )
        assert bad.kind == "chat"
        boom = await task_router.classify(
            "some vague thing xyzzy",
            llm_classifier=_raising,
        )
        assert boom.kind == "chat"

    async def _raising(text):
        raise RuntimeError("down")

    asyncio.run(go())


# -- orchestrator decisions ----------------------------------------------
@dataclass
class FakeMsg:
    content: str
    channel: str = "cli"
    chat_id: str = "main"
    metadata: dict = field(default_factory=dict)


@dataclass
class FakeOutbound:
    content: str
    metadata: dict = field(default_factory=dict)


class FakeAgent:
    full_config = None

    async def _get_conversation_state(self, channel, chat_id):
        raise AssertionError("should not be called in decision-only tests")


def test_orchestrator_trivial_fallback_decision():
    orch = Orchestrator(FakeAgent())
    decision = asyncio.run(orch.decide("bonjour"))
    assert decision.direct_fallback and decision.kind == "chat"


def test_orchestrator_nontrivial_delegates_by_default():
    orch = Orchestrator(FakeAgent())
    decision = asyncio.run(orch.decide("debug this traceback in app.py"))
    assert not decision.direct_fallback and decision.kind == "code"


def test_orchestrator_fallback_disabled_never_direct():
    orch = Orchestrator(
        FakeAgent(), settings=OrchestratorSettings(allow_direct_fallback=False)
    )
    decision = asyncio.run(orch.decide("salut"))
    assert not decision.direct_fallback


def test_orchestrator_process_message_uses_fallback_runner_for_trivial():
    calls = []

    async def runner(msg):
        calls.append(msg.content)
        return FakeOutbound(content="hello!")

    orch = Orchestrator(FakeAgent())
    out = asyncio.run(
        orch.process_message(FakeMsg(content="salut"), fallback_runner=runner)
    )
    assert isinstance(out, FakeOutbound) and calls == ["salut"]


def test_orchestrator_process_message_none_without_runner():
    orch = Orchestrator(FakeAgent())
    assert asyncio.run(orch.process_message(FakeMsg(content="salut"))) is None


# -- subagent helpers ------------------------------------------------------
def test_build_instruction_scopes_task():
    text = build_instruction("do the thing", kind="code")
    assert "kind=code" in text and "do the thing" in text


def test_collect_context_slice_skips_system_and_tool():
    @dataclass
    class M:
        role: str
        content: str

    out = collect_context_slice(
        [
            M(role="system", content="secret prompt"),
            M(role="user", content="hello"),
            M(role="tool", content="blob"),
            M(role="assistant", content="hi there"),
        ]
    )
    assert "secret prompt" not in out and "blob" not in out
    assert "hello" in out and "hi there" in out


def test_depth_guard_blocks_redelegation():
    assert is_delegation_allowed(0, 1)
    assert not is_delegation_allowed(1, 1)


def test_toolsets_filtering_contract():
    assert normalize_toolsets("coding") == ["coding"]
    with pytest.raises(ValueError):
        normalize_toolsets("nope")
    assert "shell" not in filter_tool_names(["read_file", "shell"], ["minimal"])
    assert "shell" in filter_tool_names(["read_file", "shell"], ["coding"])
