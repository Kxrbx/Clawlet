"""Telegram callback query dispatch helpers."""

from __future__ import annotations


async def dispatch_callback_query(channel, update, query, data: str) -> bool:
    chat_id = str(query.message.chat.id)

    if data == "menu:main":
        await channel._edit_callback_message(query, channel._render_help_card(), channel._main_menu_markup())
        return True
    if data == "menu:settings":
        await channel._edit_callback_message(query, channel._render_settings_card(chat_id), channel._settings_menu_markup(chat_id))
        return True
    if data == "action:status":
        await channel._edit_callback_message(query, channel._render_status_card(chat_id), channel._main_menu_markup())
        return True
    if data == "action:new":
        if channel.agent:
            await channel.agent.clear_conversation(channel.name, chat_id)
        await channel._edit_callback_message(query, "Conversation reset for this chat.", channel._main_menu_markup())
        return True
    if data == "action:memory":
        await channel._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content="Summarize the current memory and relevant context for this conversation.",
            metadata={"telegram_callback": data},
        )
        return True
    if data == "action:heartbeat":
        await channel._edit_callback_message(query, channel._render_heartbeat_card(chat_id), channel._main_menu_markup())
        return True
    if data.startswith("settings:stream_mode:"):
        mode = channel._normalize_stream_mode(data.rsplit(":", 1)[-1])
        state = channel._ensure_chat_state(chat_id)
        state["stream_mode"] = mode
        channel._save_ui_state()
        await channel._edit_callback_message(query, channel._render_settings_card(chat_id), channel._settings_menu_markup(chat_id))
        return True
    if data.startswith("approval:approve:"):
        token = data.rsplit(":", 1)[-1]
        await channel._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content=f"confirm {token}",
            metadata={"telegram_callback": data, "approval_token": token},
        )
        channel._forget_pending_approval(chat_id, token)
        await channel._edit_callback_message(query, "Approval sent. Waiting for the agent to continue.", None)
        return True
    if data.startswith("approval:reject:"):
        await channel._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content="cancel",
            metadata={"telegram_callback": data},
        )
        channel._forget_pending_approval(chat_id)
        await channel._edit_callback_message(query, "Pending action rejected.", None)
        return True
    if data.startswith("approval:details:"):
        token = data.rsplit(":", 1)[-1]
        details = channel._pending_approval_details(chat_id, token)
        if details:
            await query.answer(details[:180], show_alert=True)
        else:
            await query.answer("Approval details are no longer available.", show_alert=True)
        return True
    return False
