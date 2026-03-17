"""Telegram-specific action dispatch helpers."""

from __future__ import annotations


async def dispatch_text_menu_action(channel, update, action: str) -> bool:
    synthetic_update = update
    context = type("_Context", (), {"args": []})()

    if action == "status":
        await channel._handle_status(synthetic_update, context)
        return True
    if action == "settings":
        await channel._handle_settings(synthetic_update, context)
        return True
    if action == "memory":
        await channel._handle_memory(synthetic_update, context)
        return True
    if action == "heartbeat":
        await channel._handle_heartbeat(synthetic_update, context)
        return True
    if action == "approve":
        await channel._handle_approve(synthetic_update, context)
        return True
    if action == "cancel":
        await channel._handle_cancel(synthetic_update, context)
        return True
    if action == "new":
        await channel._handle_new(synthetic_update, context)
        return True
    if action == "stop":
        await channel._handle_stop(synthetic_update, context)
        return True
    return False
