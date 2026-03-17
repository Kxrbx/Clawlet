"""Run prelude helpers for input normalization and short-circuit handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(slots=True)
class RunPreludeResult:
    user_message: str
    persist_metadata: dict
    short_response: str | None = None


@dataclass(slots=True)
class RunPrelude:
    run_lifecycle: Any
    maybe_handle_confirmation_reply: Callable[..., Awaitable[str | None]]
    maybe_handle_direct_skill_install: Callable[[str, list[Any]], Awaitable[str | None]]
    queue_persist: Callable[[str, str, str, dict | None], None]
    logger: Any
    message_cls: type

    async def prepare(
        self,
        *,
        session_id: str,
        channel: str,
        chat_id: str,
        user_message: str,
        metadata: dict,
        source: str,
        is_heartbeat: bool,
        scheduled_payload: dict | None,
        heartbeat_ack_max_chars: int,
        history: list[Any],
        convo_key: str,
        is_internal_autonomous: bool,
        engine: str,
        engine_resolved: str,
    ) -> RunPreludeResult:
        self.run_lifecycle.start_run(
            session_id=session_id,
            channel=channel,
            chat_id=chat_id,
            engine=engine,
            engine_resolved=engine_resolved,
            source=source,
            is_heartbeat=is_heartbeat,
            message_preview=user_message,
            metadata=metadata,
            scheduled_payload=scheduled_payload,
        )

        normalized_message = user_message
        if len(normalized_message) > 10000:
            self.logger.warning(f"Message from {chat_id} exceeds 10k chars, truncating")
            normalized_message = normalized_message[:10000]

        self.logger.info(f"Processing message from {channel}/{chat_id}: {normalized_message[:50]}...")

        approval_response = await self.maybe_handle_confirmation_reply(
            convo_key=convo_key,
            session_id=session_id,
            user_message=normalized_message,
            history=history,
        )
        if approval_response is not None:
            self.run_lifecycle.complete_short_run(
                session_id=session_id,
                response_text=approval_response,
                scheduled_payload=scheduled_payload,
            )
            return RunPreludeResult(
                user_message=normalized_message,
                persist_metadata={},
                short_response=approval_response,
            )

        persist_metadata = {"heartbeat": is_heartbeat, "source": source}
        if is_internal_autonomous:
            history.append(self.message_cls(role="system", content=normalized_message))
        else:
            history.append(self.message_cls(role="user", content=normalized_message))
            self.queue_persist(session_id, "user", normalized_message, persist_metadata)

        direct_install_response = await self.maybe_handle_direct_skill_install(normalized_message, history)
        if direct_install_response is not None:
            history.append(self.message_cls(role="assistant", content=direct_install_response))
            self.queue_persist(session_id, "assistant", direct_install_response, persist_metadata)
            self.run_lifecycle.complete_short_run(
                session_id=session_id,
                response_text=direct_install_response,
                scheduled_payload=scheduled_payload,
            )
            return RunPreludeResult(
                user_message=normalized_message,
                persist_metadata=persist_metadata,
                short_response=direct_install_response,
            )

        return RunPreludeResult(
            user_message=normalized_message,
            persist_metadata=persist_metadata,
        )
