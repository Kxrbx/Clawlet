"""Turn-level intent heuristics and response-shaping policy for the agent loop.

Behavior-only mixin: all state lives on :class:`~clawlet.agent.loop.AgentLoop`
(including the TOOL_INTENT_PATTERNS / AUTONOMOUS_* / CONTINUATION_PATTERN
class constants these heuristics read via ``self``).
"""

from __future__ import annotations

import re
from typing import Optional

from loguru import logger

from clawlet.agent.models import Message


class TurnPolicyMixin:
    """Decide when tools run, whether a reply is actionable, and how it is shaped."""

    def _should_enable_tools(self, user_message: str) -> bool:
        """Enable tools for most requests; disable only trivial chat/acks."""
        text = user_message.strip()
        if not text:
            return False

        lowered = text.lower()
        normalized = lowered.rstrip("!?. ").strip()
        if self._is_trivial_chat_message(lowered):
            return False
        if normalized and self._is_trivial_chat_message(normalized):
            return False

        if self._is_ack_message(lowered):
            return False
        if normalized and self._is_ack_message(normalized):
            return False

        return True

    def _has_recent_incomplete_action_context(self, history: list[Message]) -> bool:
        """True when recent assistant replies indicate an unfinished action flow."""
        for msg in reversed(history[-6:]):
            if msg.role == "user" and self._is_action_intent(msg.content or ""):
                return True
            if msg.role != "assistant":
                continue
            content = (msg.content or "").strip()
            if not content:
                return True
            if self._looks_like_incomplete_followthrough(content, tool_calls_used=0):
                return True
            lowered = content.lower()
            if (
                "i'd love to" in lowered
                or "let me check" in lowered
                or "need to check" in lowered
                or "don't see a direct tool" in lowered
                or "i can do that" in lowered
            ):
                return True
        return False

    def _fallback_empty_response(self, *, action_intent: bool, is_heartbeat: bool) -> str:
        """Never surface an empty assistant reply to channels."""
        if is_heartbeat:
            return "HEARTBEAT_OK"
        if action_intent:
            return (
                "I got stuck before completing the action. "
                "Please retry, or start a new conversation so I can run it cleanly."
            )
        return "I got stuck and produced an empty reply. Please try again."

    def _sanitize_conversation_history(self, history: list[Message]) -> None:
        """Drop malformed tool artifacts that poison later prompts."""
        if not history:
            return
        sanitized: list[Message] = []
        removed = 0
        for msg in history:
            if msg.role == "tool" and not (msg.metadata or {}).get("tool_call_id"):
                removed += 1
                continue
            sanitized.append(msg)
        if removed:
            history[:] = sanitized
            logger.info(f"Removed {removed} malformed tool message(s) from conversation history")

    def _is_trivial_chat_message(self, lowered_text: str) -> bool:
        """True for short, non-actionable conversational turns."""
        return lowered_text in {
            "hi",
            "hello",
            "hey",
            "thanks",
            "thank you",
            "ok",
            "okay",
            "yes",
            "no",
            "how are you",
            "how are you?",
        }

    def _is_ack_message(self, lowered_text: str) -> bool:
        """True for acknowledgements that should not trigger tools."""
        return lowered_text in {
            "merci",
            "thanks",
            "thank you",
            "ok merci",
            "ok thanks",
            "super",
            "parfait",
            "top",
        }

    def _is_action_intent(self, text: str) -> bool:
        """Broad detector for requests that likely require taking actions."""
        lowered = (text or "").strip().lower()
        if not lowered:
            return False
        if self._is_trivial_chat_message(lowered) or self._is_ack_message(lowered):
            return False
        for pattern in self.TOOL_INTENT_PATTERNS:
            if re.search(pattern, lowered, re.IGNORECASE):
                return True
        return bool(self.URL_PATTERN.search(lowered))

    def _should_schedule_autonomous_followup(
        self,
        assistant_response: str,
        tool_calls_used: int,
        is_error: bool,
        is_internal_autonomous: bool,
        autonomous_depth: int,
    ) -> bool:
        """Schedule a self-follow-up turn if the model promised action but did none."""
        if is_error:
            return False
        if is_internal_autonomous:
            return False
        if autonomous_depth >= self.MAX_AUTONOMOUS_FOLLOWUP_DEPTH:
            return False
        if tool_calls_used > 0:
            return False

        text = (assistant_response or "").strip()
        if not text:
            return False

        # If model is asking for input/confirmation, do not force autonomous continuation.
        if "?" in text or self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return False

        return bool(self.AUTONOMOUS_COMMITMENT_PATTERN.search(text))

    def _looks_like_incomplete_followthrough(self, text: str, tool_calls_used: int) -> bool:
        """Detect mid-task narration that should stay inside the current turn."""
        text = (text or "").strip()
        if not text:
            return False
        if "?" in text or self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return False
        if self.AUTONOMOUS_COMMITMENT_PATTERN.search(text):
            return True
        if tool_calls_used <= 0:
            return False
        return bool(self.CONTINUATION_PATTERN.search(text))

    def _looks_like_blocker_response(self, text: str) -> bool:
        """Heuristic for responses that are acceptable stop points after tools."""
        text = (text or "").strip()
        if not text:
            return False
        if "?" in text:
            return True
        if self.AUTONOMOUS_BLOCKING_PATTERN.search(text):
            return True
        lowered = text.lower()
        blocker_markers = (
            "could not",
            "can't",
            "cannot",
            "unable",
            "failed",
            "error",
            "blocked",
            "requires",
            "need your",
            "manual step",
            "manual action",
            "claim step",
            "verification",
        )
        return any(marker in lowered for marker in blocker_markers)
