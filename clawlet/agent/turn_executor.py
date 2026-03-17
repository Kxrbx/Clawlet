"""Turn execution engine for provider/tool iteration outside AgentLoop shell."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from clawlet.agent.heartbeat_turn import HeartbeatTurnHandler
from clawlet.agent.models import Message, ToolCall
from clawlet.tools.registry import ToolResult


@dataclass(slots=True)
class TurnOutcome:
    final_response: str
    is_error: bool
    iterations: int
    tool_calls_used: int
    action_intent: bool
    final_metadata_extra: dict
    heartbeat_tool_names: list[str]
    heartbeat_blockers: list[str]
    heartbeat_action_summaries: list[str]


@dataclass(slots=True)
class TurnExecutor:
    agent: Any
    heartbeat_handler: HeartbeatTurnHandler

    async def execute(
        self,
        *,
        convo: Any,
        user_message: str,
        persist_metadata: dict,
        run_ctx: Any,
        convo_key: str,
        is_internal_autonomous: bool,
        autonomous_depth: int,
    ) -> TurnOutcome:
        is_heartbeat = run_ctx.is_heartbeat
        self.agent._trim_history(convo.history)
        self.agent._sanitize_conversation_history(convo.history)

        iteration = 0
        final_response = None
        is_error = False
        no_progress_count = 0
        last_signature: str | None = None
        enable_tools = self.agent._should_enable_tools(user_message)
        tool_gate_promoted = False
        action_nudge_used = False
        commitment_followthrough_used = False
        post_tool_finalization_used = False
        tool_calls_used = 0
        final_metadata_extra: dict = {}
        executed_tool_signatures: set[str] = set()
        heartbeat_tool_names: list[str] = []
        heartbeat_blockers: list[str] = []
        heartbeat_action_summaries: list[str] = []
        explicit_urls = self.agent._extract_explicit_urls(user_message)
        explicit_github_url = self.agent._extract_github_url(user_message)
        install_skill_intent = self.agent._is_skill_install_intent(user_message)
        followup_action_context = self.agent._has_recent_incomplete_action_context(convo.history)
        action_intent = self.agent._is_action_intent(user_message) or followup_action_context
        if followup_action_context and not enable_tools:
            logger.info("Promoting follow-up turn to tools-enabled due to recent unfinished action context")
            enable_tools = True
        iteration_limit = run_ctx.mode.iteration_limit if run_ctx.mode else self.agent.max_iterations
        tool_call_limit = run_ctx.mode.tool_call_limit if run_ctx.mode else self.agent.max_tool_calls_per_message
        no_progress_limit = run_ctx.mode.no_progress_limit if run_ctx.mode else self.agent.NO_PROGRESS_LIMIT

        await self.agent._publish_progress_update("started", "Starting work on your request.")

        while iteration < iteration_limit:
            iteration += 1
            self.agent._save_checkpoint(stage="iteration", iteration=iteration, notes="Starting model iteration")
            messages = self.agent._build_messages(
                convo.history,
                query_hint=user_message,
                is_heartbeat=is_heartbeat,
            )
            try:
                await self.agent._publish_progress_update("provider_started", "Thinking about the next step.")
                response = await self.agent._call_provider_with_retry(messages, enable_tools=enable_tools)
                self.agent._save_checkpoint(stage="provider_response", iteration=iteration, notes="Model response received")
                response_content = response.content
                tool_calls = self._normalize_tool_calls(
                    response_content=response_content,
                    response=response,
                    install_skill_intent=install_skill_intent,
                    explicit_github_url=explicit_github_url,
                    explicit_urls=explicit_urls,
                    tool_calls_used=tool_calls_used,
                )
                tool_calls, repeated_only = self._dedupe_and_filter_tool_calls(
                    tool_calls=tool_calls,
                    executed_tool_signatures=executed_tool_signatures,
                    convo=convo,
                    user_message=user_message,
                    is_heartbeat=is_heartbeat,
                    tool_calls_used=tool_calls_used,
                )
                if repeated_only:
                    continue

                signature = json.dumps(
                    {
                        "content": response_content[:500],
                        "tool_calls": [{"name": t.name, "args": t.arguments} for t in tool_calls],
                    },
                    sort_keys=True,
                )
                if signature == last_signature:
                    no_progress_count += 1
                else:
                    no_progress_count = 0
                last_signature = signature

                if no_progress_count >= no_progress_limit and not tool_calls:
                    logger.warning("Stopping loop due to repeated no-progress model responses")
                    final_response = "I am stuck repeating the same step. Please refine your request."
                    is_error = True
                    break

                if tool_calls:
                    final_response, is_error, tool_gate_promoted, final_metadata_extra, tool_calls_used = await self._handle_tool_calls(
                        convo=convo,
                        convo_key=convo_key,
                        user_message=user_message,
                        persist_metadata=persist_metadata,
                        response_content=response_content,
                        tool_calls=tool_calls,
                        enable_tools=enable_tools,
                        tool_gate_promoted=tool_gate_promoted,
                        tool_call_limit=tool_call_limit,
                        tool_calls_used=tool_calls_used,
                        executed_tool_signatures=executed_tool_signatures,
                        is_heartbeat=is_heartbeat,
                        heartbeat_tool_names=heartbeat_tool_names,
                        heartbeat_blockers=heartbeat_blockers,
                        heartbeat_action_summaries=heartbeat_action_summaries,
                        iteration=iteration,
                    )
                    if final_response == "__continue_with_tools_enabled__":
                        final_response = None
                        enable_tools = True
                        continue
                    if final_response is not None:
                        break
                    continue

                if not tool_calls and is_heartbeat:
                    heartbeat_text = self.heartbeat_handler.maybe_accept_text_only_response(
                        response_content,
                        tool_calls_used,
                    )
                    if heartbeat_text is not None:
                        convo.history.append(Message(role="assistant", content=heartbeat_text))
                        self.agent._queue_persist(convo.session_id, "assistant", heartbeat_text, persist_metadata)
                        final_response = heartbeat_text
                        break

                if enable_tools and action_intent and tool_calls_used == 0 and not action_nudge_used:
                    logger.info("Action intent detected with no tool calls; nudging model to use tools")
                    action_nudge_used = True
                    convo.history.append(
                        Message(
                            role="system",
                            content=(
                                "This request is actionable. Use available tools when needed, "
                                "then provide the final answer. Do not output tool-call markup."
                            ),
                        )
                    )
                    continue

                if (
                    not tool_calls
                    and enable_tools
                    and self.agent._looks_like_incomplete_followthrough(response_content, tool_calls_used)
                ):
                    if not commitment_followthrough_used:
                        logger.info("Model returned mid-task narration without action; forcing same-turn follow-through")
                        commitment_followthrough_used = True
                        convo.history.append(
                            Message(role="system", content=self.agent.COMMITMENT_FOLLOWTHROUGH_NUDGE)
                        )
                        continue
                    if is_internal_autonomous:
                        logger.warning(
                            "Internal autonomous follow-up still returned mid-task narration after forced follow-through"
                        )
                        final_response = (
                            "I could not complete the promised action automatically because no executable step was taken. "
                            "Please retry the request or ask me to perform one concrete action."
                        )
                        is_error = True
                        break
                    logger.warning(
                        "Model still returned mid-task narration after forced follow-through; refusing to send partial status"
                    )
                    final_response = (
                        "I did not execute the promised action. Please retry with one concrete action, "
                        "or I can try again with a more specific next step."
                    )
                    is_error = True
                    break

                if (
                    not tool_calls
                    and enable_tools
                    and tool_calls_used > 0
                    and not post_tool_finalization_used
                    and not self.agent._looks_like_blocker_response(response_content)
                ):
                    logger.info("Suppressing post-tool intermediate narration; forcing one finalization pass")
                    await self.agent._publish_progress_update("finalizing", "Finalizing the response.")
                    post_tool_finalization_used = True
                    convo.history.append(Message(role="system", content=self.agent.POST_TOOL_FINALIZATION_NUDGE))
                    continue

                if (
                    is_internal_autonomous
                    and enable_tools
                    and not tool_calls
                    and self.agent.AUTONOMOUS_COMMITMENT_PATTERN.search(response_content or "")
                ):
                    if not action_nudge_used:
                        logger.info(
                            "Internal autonomous follow-up returned another commitment without tool calls; nudging model to execute now or report blocker"
                        )
                        action_nudge_used = True
                        convo.history.append(Message(role="system", content=self.agent.AUTONOMOUS_EXECUTION_NUDGE))
                        continue
                    logger.warning(
                        "Internal autonomous follow-up still returned a commitment with no tool calls after nudge"
                    )
                    final_response = (
                        "I could not complete the promised action automatically because no executable step was taken. "
                        "Please retry the request or ask me to perform one concrete action."
                    )
                    is_error = True
                    break

                final_text = self.agent._sanitize_final_response(response_content, tool_calls_used)
                convo.history.append(Message(role="assistant", content=final_text or response_content))
                self.agent._queue_persist(convo.session_id, "assistant", final_text or response_content, persist_metadata)
                final_response = final_text or response_content
                break
            except Exception as e:
                logger.error(f"Error in agent loop iteration {iteration}: {e}")
                self.agent._save_checkpoint(stage="error", iteration=iteration, notes=str(e))
                final_response = self.agent._format_user_facing_error(e)
                is_error = True
                break

        if final_response is None:
            final_response, is_error = await self._run_finalization_pass(
                convo=convo,
                user_message=user_message,
                persist_metadata=persist_metadata,
                tool_calls_used=tool_calls_used,
                is_heartbeat=is_heartbeat,
            )

        if final_response is None:
            final_response = "I reached my maximum number of iterations. Please try again."
            is_error = True
        elif not str(final_response).strip():
            final_response = self.agent._fallback_empty_response(
                action_intent=action_intent,
                is_heartbeat=is_heartbeat,
            )
            is_error = True

        if not (final_response or "").strip():
            if action_intent:
                final_response = (
                    "I could not complete that action in this turn. "
                    "I hit an execution failure before producing a usable result."
                )
            else:
                final_response = "I couldn't produce a usable reply for that message."
            is_error = True

        if is_heartbeat:
            final_response, is_error = self.heartbeat_handler.finalize_response(
                response_text=final_response,
                is_error=is_error,
                tool_names=heartbeat_tool_names,
                blockers=heartbeat_blockers,
                action_summaries=heartbeat_action_summaries,
            )

        return TurnOutcome(
            final_response=final_response,
            is_error=is_error,
            iterations=iteration,
            tool_calls_used=tool_calls_used,
            action_intent=action_intent,
            final_metadata_extra=final_metadata_extra,
            heartbeat_tool_names=heartbeat_tool_names,
            heartbeat_blockers=heartbeat_blockers,
            heartbeat_action_summaries=heartbeat_action_summaries,
        )

    def _normalize_tool_calls(
        self,
        *,
        response_content: str,
        response: Any,
        install_skill_intent: bool,
        explicit_github_url: str | None,
        explicit_urls: list[str],
        tool_calls_used: int,
    ) -> list[ToolCall]:
        tool_calls = self.agent._extract_provider_tool_calls(response)
        if not tool_calls:
            tool_calls = self.agent._extract_tool_calls(response_content)
        tool_calls = self.agent._dedupe_tool_calls(tool_calls)
        if (
            not tool_calls
            and install_skill_intent
            and explicit_github_url
            and tool_calls_used == 0
            and self.agent.tools.get("install_skill") is not None
        ):
            logger.info(
                "Applying install-first policy: model returned no tool call, "
                f"forcing install_skill for {explicit_github_url}"
            )
            tool_calls = [ToolCall(id="forced_install_skill_missing_tool_call", name="install_skill", arguments={"github_url": explicit_github_url})]
        if (
            not tool_calls
            and explicit_urls
            and tool_calls_used == 0
            and self.agent.tools.get("fetch_url") is not None
            and not self.agent._is_authenticated_api_url(explicit_urls[0])
        ):
            logger.info(
                "Applying URL-first policy: model returned no tool call, "
                f"forcing fetch_url for {explicit_urls[0]}"
            )
            tool_calls = [ToolCall(id="forced_fetch_url_missing_tool_call", name="fetch_url", arguments={"url": explicit_urls[0]})]
        return self.agent._prioritize_explicit_url_fetch(
            tool_calls=tool_calls,
            explicit_urls=explicit_urls,
            tool_calls_used=tool_calls_used,
        )

    def _dedupe_and_filter_tool_calls(
        self,
        *,
        tool_calls: list[ToolCall],
        executed_tool_signatures: set[str],
        convo: Any,
        user_message: str,
        is_heartbeat: bool,
        tool_calls_used: int,
    ) -> tuple[list[ToolCall], bool]:
        repeated_tool_calls: list[ToolCall] = []
        novel_tool_calls: list[ToolCall] = []
        for tc in tool_calls:
            signature = self.agent._tool_call_signature(tc)
            if signature in executed_tool_signatures:
                repeated_tool_calls.append(tc)
                continue
            novel_tool_calls.append(tc)
        if repeated_tool_calls:
            logger.warning(
                "Skipping repeated tool call(s) in same turn: "
                f"{[t.name for t in repeated_tool_calls]}"
            )
            if not novel_tool_calls:
                convo.history.append(
                    Message(
                        role="system",
                        content=(
                            "You already executed that exact tool call in this turn. "
                            "Reuse previous tool outputs from conversation history and do not repeat identical calls."
                        ),
                    )
                )
                return [], True
        filtered_tool_calls: list[ToolCall] = []
        blocked_exploration = False
        for tc in novel_tool_calls:
            if self.agent._is_low_value_exploration_tool(
                tool_call=tc,
                user_message=user_message,
                is_heartbeat=is_heartbeat,
                tool_calls_used=tool_calls_used,
            ):
                blocked_exploration = True
                logger.info(
                    "Blocked low-value exploration tool call during action-oriented task: "
                    f"{tc.name} {tc.arguments}"
                )
                continue
            filtered_tool_calls.append(tc)
        if blocked_exploration and not filtered_tool_calls:
            convo.history.append(
                Message(
                    role="system",
                    content=(
                        "Do not inspect config files, list installed skills, or browse workspace roots "
                        "before attempting the requested external action. Use the minimum direct tool step needed. "
                        "Do not read credentials files manually; authenticated HTTP tools resolve saved credentials automatically."
                    ),
                )
            )
            return [], True
        return filtered_tool_calls, False

    async def _handle_tool_calls(
        self,
        *,
        convo: Any,
        convo_key: str,
        user_message: str,
        persist_metadata: dict,
        response_content: str,
        tool_calls: list[ToolCall],
        enable_tools: bool,
        tool_gate_promoted: bool,
        tool_call_limit: int,
        tool_calls_used: int,
        executed_tool_signatures: set[str],
        is_heartbeat: bool,
        heartbeat_tool_names: list[str],
        heartbeat_blockers: list[str],
        heartbeat_action_summaries: list[str],
        iteration: int,
    ) -> tuple[str | None, bool, bool, dict, int]:
        tool_names = ", ".join(tc.name for tc in tool_calls[:4])
        if len(tool_calls) > 4:
            tool_names += ", ..."
        await self.agent._publish_progress_update(
            "tool_requested",
            f"Preparing {len(tool_calls)} tool call(s).",
            detail=tool_names,
        )
        if not enable_tools:
            if (
                not tool_gate_promoted
                and self.agent._should_promote_tools_for_parsed_calls(
                    user_message,
                    tool_calls,
                    history=convo.history,
                )
            ):
                logger.info("Parsed tool calls while tools were disabled; promoting this request to tools-enabled and retrying")
                return "__continue_with_tools_enabled__", False, True, {}, tool_calls_used
            logger.warning("Ignoring tool calls because tools are disabled for this request")
            cleaned = self.agent._response_policy.strip_tool_call_markup(response_content)
            if not cleaned and "<tool_call" in (response_content or "").lower():
                cleaned = (
                    "I detected an action-style tool call but tools are disabled for this turn. "
                    "Please ask with an explicit action request."
                )
            if cleaned and cleaned != response_content:
                convo.history.append(Message(role="assistant", content=cleaned))
                self.agent._queue_persist(convo.session_id, "assistant", cleaned, persist_metadata)
                return cleaned, False, tool_gate_promoted, {}, tool_calls_used
            return None, False, tool_gate_promoted, {}, tool_calls_used

        if tool_calls_used + len(tool_calls) > tool_call_limit:
            logger.warning(
                "Stopping loop due to tool-call budget exceeded: "
                f"{tool_calls_used + len(tool_calls)} > {tool_call_limit}"
            )
            return (
                "I stopped to avoid excessive tool calls. Please narrow the request and I will run only the minimum needed actions.",
                True,
                tool_gate_promoted,
                {},
                tool_calls_used,
            )

        tool_calls_used += len(tool_calls)
        self.agent._tool_stats["calls_requested"] += len(tool_calls)
        convo.history.append(
            Message(
                role="assistant",
                content=response_content,
                tool_calls=[
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in tool_calls
                ],
            )
        )
        self.agent._queue_persist(convo.session_id, "assistant", response_content, persist_metadata)

        mapped_calls: list[ToolCall] = []
        for tc in tool_calls:
            requested_tool_name = tc.name
            mapped_tool_name = self.agent._tool_aliases.get(requested_tool_name, requested_tool_name)
            if mapped_tool_name != requested_tool_name:
                logger.info(f"Mapping tool alias '{requested_tool_name}' -> '{mapped_tool_name}'")
            tc.name = mapped_tool_name
            mapped_calls.append(self.agent._rewrite_specialized_tool_call(tc))
        if is_heartbeat:
            heartbeat_tool_names.extend([tc.name for tc in mapped_calls])
        for tc in mapped_calls:
            executed_tool_signatures.add(self.agent._tool_call_signature(tc))

        for tc in mapped_calls:
            confirm_reason = self.agent._requires_confirmation(tc)
            if confirm_reason:
                token = self.agent._approval_service.mint_token()
                self.agent._approval_service.set(convo_key, token, tc)
                return (
                    f"{confirm_reason}: `{tc.name}`.\nReply with `confirm {token}` to continue or `cancel`.",
                    False,
                    tool_gate_promoted,
                    self.agent._approval_service.build_confirmation_outbound_metadata(
                        token=token,
                        tool_call=tc,
                        reason=confirm_reason,
                    ),
                    tool_calls_used,
                )

        executed = await self.agent._execute_tool_calls_optimized(mapped_calls)
        for tc, result in executed:
            self._append_tool_result(
                convo=convo,
                persist_metadata=persist_metadata,
                tc=tc,
                result=result,
                is_heartbeat=is_heartbeat,
                heartbeat_blockers=heartbeat_blockers,
                heartbeat_action_summaries=heartbeat_action_summaries,
                iteration=iteration,
            )
        return None, False, tool_gate_promoted, {}, tool_calls_used

    def _append_tool_result(
        self,
        *,
        convo: Any,
        persist_metadata: dict,
        tc: ToolCall,
        result: ToolResult,
        is_heartbeat: bool,
        heartbeat_blockers: list[str],
        heartbeat_action_summaries: list[str],
        iteration: int,
    ) -> None:
        rendered_tool_output = self.agent._render_tool_result(result)
        if is_heartbeat and not result.success and (result.error or result.output):
            heartbeat_blockers.append((result.error or result.output)[:280])
        if is_heartbeat:
            action_summary = self.agent._summarize_heartbeat_tool_result(tc.name, result)
            if action_summary:
                heartbeat_action_summaries.append(action_summary)
        self.agent._save_checkpoint(stage="tool_executed", iteration=iteration, notes=f"tool={tc.name} success={result.success}")
        convo.history.append(
            Message(
                role="tool",
                content=rendered_tool_output,
                metadata={"tool_call_id": tc.id, "tool_name": tc.name},
            )
        )
        self.agent._queue_persist(convo.session_id, "tool", rendered_tool_output)

    async def _run_finalization_pass(
        self,
        *,
        convo: Any,
        user_message: str,
        persist_metadata: dict,
        tool_calls_used: int,
        is_heartbeat: bool,
    ) -> tuple[str | None, bool]:
        if tool_calls_used <= 0:
            return None, False
        logger.info("Iteration cap reached after tool use; attempting one finalization-only pass")
        try:
            await self.agent._publish_progress_update("finalizing", "Summarizing completed work and any blockers.")
            convo.history.append(
                Message(
                    role="system",
                    content=(
                        "This is the final response pass for this turn. "
                        "Do not call more tools. Summarize what was completed and any concrete blocker that remains."
                    ),
                )
            )
            messages = self.agent._build_messages(
                convo.history,
                query_hint=user_message,
                is_heartbeat=is_heartbeat,
            )
            response = await self.agent._call_provider_with_retry(messages, enable_tools=False)
            response_content = self.agent._sanitize_final_response(response.content or "", tool_calls_used).strip()
            if response_content:
                convo.history.append(Message(role="assistant", content=response_content))
                self.agent._queue_persist(convo.session_id, "assistant", response_content, persist_metadata)
                return response_content, self.agent._looks_like_blocker_response(response_content)
        except Exception as e:
            logger.error(f"Error in finalization-only pass: {e}")
        return None, False
