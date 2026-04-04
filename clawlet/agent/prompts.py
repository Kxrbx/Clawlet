"""Shared prompt and nudge constants for agent turn execution."""

AUTONOMOUS_EXECUTION_NUDGE = (
    "Autonomous execution mode: do not promise future action. "
    "Either use tools now to perform the task, or reply with a concrete blocker explaining why "
    "the action could not be executed automatically."
)

COMMITMENT_FOLLOWTHROUGH_NUDGE = (
    "Do not narrate future action. "
    "If you said you would do something, perform the next concrete step now using tools when needed. "
    "Only reply to the user after you have either completed the action or hit a concrete blocker."
)

POST_TOOL_FINALIZATION_NUDGE = (
    "You have already used tools in this turn. "
    "Do not send intermediate status updates or describe next steps. "
    "Either provide the final answer grounded in the tool results you already have, "
    "or explain the concrete blocker that prevents completion."
)

HEARTBEAT_ACTION_POLICY = (
    "Heartbeat poll policy:\n"
    "- Follow the heartbeat prompt strictly.\n"
    "- Do not infer or repeat old tasks from prior chats.\n"
    "- Read HEARTBEAT.md first when the prompt requires it.\n"
    "- Prefer `http_request` over shell/curl for API calls and JSON posts.\n"
    "- Use `review_daily_notes` before curating long-term memory, and use `curate_memory` when recent notes contain durable updates.\n"
    "- If nothing needs attention, reply exactly with HEARTBEAT_OK.\n"
    "- Avoid unrelated exploration unless the heartbeat task is blocked."
)
