"""Always-on orchestrator — every non-trivial request goes through sub-agents.

Pipeline per inbound message::

    classify (hybrid rules + optional LLM)
      -> trivial + fallback allowed? run parent turn directly (traced)
      -> else spawn child worker (profile provider/model/toolset/budget)
      -> run child turn through the standard run pipeline
      -> attribute output (task_kind/child_session_id metadata)

Children run through :class:`RunOrchestrator` on their own loop instance,
so zero changes to the turn pipeline were required. Children never
re-delegate (depth guard in :mod:`clawlet.agent.subagent`).
"""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from clawlet.agent import task_router
from clawlet.agent.subagent import (
    SubagentSpec,
    build_instruction,
    collect_context_slice,
    is_delegation_allowed,
    spawn_child_loop,
)
from clawlet.agent.task_profiles import (
    TASK_KINDS,
    OrchestratorSettings,
    TaskProfile,
    resolve_profile,
)

FallbackRunner = Callable[[Any], Awaitable[Any | None]]


@dataclass(slots=True)
class OrchestrationDecision:
    kind: str
    confidence: float
    reason: str
    source: str
    direct_fallback: bool = False


@dataclass(slots=True)
class DelegationResult:
    kind: str
    output: Any | None
    profile: Any = None
    child_session_id: str = ""
    error: str = ""


class Orchestrator:
    """Wraps a parent ``AgentLoop`` and dispatches work to child workers."""

    def __init__(
        self,
        agent: Any,
        *,
        settings: OrchestratorSettings | None = None,
        task_profiles: dict[str, TaskProfile] | None = None,
        llm_classifier: Any = None,
    ):
        self.agent = agent
        self.settings = settings or OrchestratorSettings()
        self.task_profiles = task_profiles or {}
        self.llm_classifier = llm_classifier

    # -- decision ------------------------------------------------------
    async def decide(self, text: str) -> OrchestrationDecision:
        if self.settings.allow_direct_fallback and task_router.is_trivial(
            text, max_chars=self.settings.trivial_max_chars
        ):
            return OrchestrationDecision(
                kind="chat",
                confidence=0.95,
                reason="trivial direct fallback",
                source="rules",
                direct_fallback=True,
            )
        classification = await task_router.classify(
            text,
            llm_classifier=self.llm_classifier
            if self.settings.classifier_mode != "rules"
            else None,
            valid_kinds=frozenset(TASK_KINDS),
        )
        return OrchestrationDecision(
            kind=classification.kind,
            confidence=classification.confidence,
            reason=classification.reason,
            source=classification.source,
            direct_fallback=False,
        )

    # -- profile resolution --------------------------------------------
    def resolve(self, kind: str):
        global_provider = "openrouter"
        global_model = ""
        provider_cfg = None
        raw_profiles = None
        config = getattr(self.agent, "full_config", None)
        if config is None:
            config = getattr(self.agent, "config", None)
        if config is not None:
            provider_cfg = getattr(config, "provider", None)
            if provider_cfg is not None:
                global_provider = (
                    getattr(provider_cfg, "primary", "openrouter") or "openrouter"
                )
            raw_profiles = getattr(config, "task_profiles", None)
        profiles = dict(self.task_profiles)
        if isinstance(raw_profiles, dict):
            for k, v in raw_profiles.items():
                if isinstance(v, TaskProfile):
                    profiles[k] = v
                elif isinstance(v, dict):
                    try:
                        profiles[k] = TaskProfile(**v)
                    except Exception as e:
                        logger.warning(f"Ignoring invalid task profile {k!r}: {e}")
        return resolve_profile(
            kind,
            profiles,
            global_provider=global_provider,
            global_model=global_model,
        ), provider_cfg

    # -- dispatch ------------------------------------------------------
    def build_spec(
        self,
        user_message: str,
        kind: str,
        *,
        history: list | None = None,
        parent_session_id: str = "",
        parent_run_id: str = "",
        depth: int = 0,
    ) -> SubagentSpec:
        return SubagentSpec(
            kind=kind,
            instruction=build_instruction(user_message, kind=kind),
            context_slice=collect_context_slice(history or []),
            session_id=f"sub-{uuid.uuid4().hex[:12]}",
            parent_session_id=parent_session_id,
            parent_run_id=parent_run_id,
            depth=depth,
        )

    async def dispatch_single(
        self, msg: Any, decision: OrchestrationDecision
    ) -> DelegationResult:
        """Spawn one child and run the message through its standard pipeline."""
        from clawlet.agent.run_orchestrator import RunOrchestrator

        profile, _ = self.resolve(decision.kind)
        history: list = []
        parent_session = ""
        get_state = getattr(self.agent, "_get_conversation_state", None)
        if get_state is not None:
            try:
                convo = await get_state(msg.channel, msg.chat_id)
                history = list(getattr(convo, "history", []) or [])
                parent_session = str(getattr(convo, "session_id", "") or "")
            except Exception:
                parent_session = ""
        spec = self.build_spec(
            str(getattr(msg, "content", "")),
            decision.kind,
            history=history,
            parent_session_id=parent_session,
            parent_run_id=str((getattr(msg, "metadata", None) or {}).get("run_id", "")),
            depth=0,
        )
        if not is_delegation_allowed(spec.depth, self.settings.max_depth):
            return DelegationResult(
                kind=decision.kind,
                output=None,
                profile=profile,
                error="delegation depth exceeded",
            )
        try:
            child = spawn_child_loop(self.agent, spec, profile)
        except Exception as e:
            logger.error(f"Sub-agent spawn failed for kind={decision.kind}: {e}")
            return DelegationResult(
                kind=decision.kind, output=None, profile=profile, error=str(e)
            )
        await self._record_lineage(
            spec, profile, source=str(getattr(msg, "channel", "") or "")
        )
        try:
            child_msg = self._child_message(msg, spec, profile)
            result = await asyncio.wait_for(
                RunOrchestrator(child).process_message(child_msg),
                timeout=profile.timeout_s or 180.0,
            )
            return DelegationResult(
                kind=decision.kind,
                output=result,
                profile=profile,
                child_session_id=spec.session_id,
            )
        except TimeoutError:
            logger.error(f"Sub-agent timed out (kind={decision.kind})")
            return DelegationResult(
                kind=decision.kind, output=None, profile=profile, error="timeout"
            )
        except Exception as e:
            logger.error(f"Sub-agent run failed (kind={decision.kind}): {e}")
            return DelegationResult(
                kind=decision.kind, output=None, profile=profile, error=str(e)
            )

    # -- entry point ----------------------------------------------------
    async def process_message(
        self,
        msg: Any,
        fallback_runner: FallbackRunner | None = None,
    ) -> Any | None:
        """Orchestrate one inbound message.

        Returns the child/synthesized outbound, or — when the trivial
        fallback applies — the result of ``fallback_runner(msg)`` (the
        normal parent turn). ``fallback_runner=None`` + fallback decision
        returns ``None`` so the caller can run its default path.
        """
        text = str(getattr(msg, "content", "") or "")
        decision = await self.decide(text)
        logger.info(
            f"Orchestrator decision: kind={decision.kind} fallback={decision.direct_fallback} ({decision.reason})"
        )
        if decision.direct_fallback:
            if fallback_runner is None:
                return None
            return await fallback_runner(msg)
        result = await self.dispatch_single(msg, decision)
        if result.output is not None:
            self._tag_output(result)
            return result.output
        # Child failed and no fallback runner configured -> surface the error
        # as a normal reply so the user is never left hanging.
        logger.warning(
            f"Delegation failed (kind={result.kind}): {result.error}; using parent fallback"
        )
        if fallback_runner is not None:
            return await fallback_runner(msg)
        return None

    async def _record_lineage(
        self, spec: SubagentSpec, profile: Any, source: str
    ) -> None:
        """Best-effort SessionDB lineage write. Never raises."""
        try:
            storage = getattr(self.agent, "storage", None)
            db_path = getattr(storage, "db_path", None)
            if not db_path:
                return
            from clawlet.storage.session_db import SessionRecord, SessionStore

            store = SessionStore(db_path)
            await store.initialize()
            try:
                await store.record_session(
                    SessionRecord(
                        session_id=spec.session_id,
                        parent_session_id=spec.parent_session_id,
                        task_kind=spec.kind,
                        profile_snapshot=profile.as_dict()
                        if hasattr(profile, "as_dict")
                        else {},
                        source=source,
                    )
                )
            finally:
                await store.close()
        except Exception as e:
            logger.debug(f"Lineage record skipped: {e}")

    # -- internals --------------------------------------------------------
    def _child_message(self, msg: Any, spec: SubagentSpec, profile: Any) -> Any:
        """Clone the inbound message for the child with lineage metadata."""
        metadata = dict(getattr(msg, "metadata", None) or {})
        metadata.update(
            {
                "delegated_kind": spec.kind,
                "parent_session_id": spec.parent_session_id,
                "parent_run_id": spec.parent_run_id,
                "task_profile": profile.as_dict()
                if hasattr(profile, "as_dict")
                else {},
            }
        )
        try:
            return dataclasses.replace(msg, metadata=metadata)
        except Exception:
            return msg

    def _tag_output(self, result: DelegationResult) -> None:
        out = result.output
        if out is None:
            return
        metadata = getattr(out, "metadata", None)
        if isinstance(metadata, dict):
            metadata.setdefault("task_kind", result.kind)
            metadata.setdefault("child_session_id", result.child_session_id)
