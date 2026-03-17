"""
Telegram channel implementation.
"""

import asyncio
import json
import re
import time
from collections import defaultdict
from html import escape
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from telegram import BotCommand, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import BadRequest, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    from telegram import MenuButtonCommands
except ImportError:  # pragma: no cover - depends on python-telegram-bot build
    MenuButtonCommands = None

from clawlet.bus.queue import InboundMessage, MessageBus, OutboundMessage
from clawlet.channels.telegram_actions import dispatch_text_menu_action
from clawlet.channels.telegram_callbacks import dispatch_callback_query
from clawlet.channels.base import BaseChannel
from clawlet.channels.telegram_menu import resolve_text_menu_action
from clawlet.channels.telegram_ui import build_inline_keyboard, default_reply_keyboard, main_menu_markup, settings_menu_markup
from clawlet.cli.runtime_paths import get_default_workspace_path


TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_SAFE_HTML_CHUNK = 3500
STREAM_MODES = {"off", "progress", "verbose_debug"}


def convert_markdown_to_html(text: str) -> str:
    """Convert a practical subset of Markdown into Telegram-safe HTML."""
    if not text:
        return text

    text = text.replace("\r\n", "\n")
    placeholders: list[str] = []

    def _stash(tag: str, body: str) -> str:
        placeholders.append(f"<{tag}>{escape(body)}</{tag}>")
        # Keep the temporary token free of markdown metacharacters so later
        # emphasis processing cannot mutate it before restoration.
        return f"@@TGPH{len(placeholders) - 1}@@"

    text = re.sub(
        r"```(?:\w+)?\n?([\s\S]*?)```",
        lambda m: _stash("pre", m.group(1).rstrip("\n")),
        text,
    )
    text = re.sub(r"`([^`]+)`", lambda m: _stash("code", m.group(1)), text)
    text = escape(text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^_]+)__", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<i>\1</i>", text)
    text = re.sub(r"~~([^~]+)~~", r"<s>\1</s>", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)
    text = re.sub(r"^[\-\*]\s+", "• ", text, flags=re.MULTILINE)

    for index, placeholder in enumerate(placeholders):
        text = text.replace(f"@@TGPH{index}@@", placeholder)
    return text


def _prepare_html_text(text: str, *, trusted_html: bool = False) -> str:
    """Render trusted HTML verbatim, otherwise convert Markdown-ish text safely."""
    if trusted_html:
        return text or ""
    return convert_markdown_to_html(text or "")


class TelegramChannel(BaseChannel):
    """Telegram channel using python-telegram-bot."""

    def __init__(self, bus: MessageBus, config: dict, agent=None):
        super().__init__(bus, config, agent)

        self.token = (config.get("token") or "").strip()
        if not self.token:
            raise ValueError("Telegram token not configured")

        self.app: Optional[Application] = None
        self._outbound_task: Optional[asyncio.Task] = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._typing_refcounts: defaultdict[str, int] = defaultdict(int)
        self._stream_mode_default = self._normalize_stream_mode(config.get("stream_mode"))
        self._stream_update_interval = float(config.get("stream_update_interval_seconds", 1.5) or 1.5)
        self._disable_web_page_preview = bool(config.get("disable_web_page_preview", True))
        self._use_reply_keyboard = bool(config.get("use_reply_keyboard", True))
        self._register_commands = bool(config.get("register_commands", True))
        self._heartbeat_config = dict(config.get("heartbeat") or {})
        self._ui_state_path = self._resolve_ui_state_path()
        self._chat_state: dict[str, dict[str, Any]] = self._load_ui_state()

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        """Start the Telegram bot."""
        logger.info("Starting Telegram channel...")
        try:
            self.app = Application.builder().token(self.token).build()
            self._install_handlers()
            await self.app.initialize()
            await self.app.start()
            if self._register_commands:
                await self._register_telegram_commands()
            await self.app.updater.start_polling()

            self._running = True
            self._outbound_task = asyncio.create_task(self._run_outbound_loop())
            logger.info("Telegram channel started successfully")
        except Exception as e:
            if isinstance(e, AttributeError) and "_Updater__polling_cleanup_cb" in str(e):
                try:
                    ptb_version = version("python-telegram-bot")
                except PackageNotFoundError:
                    ptb_version = "unknown"
                logger.error(
                    "Telegram startup failed due to an incompatible python-telegram-bot build "
                    f"(detected version={ptb_version}). Reinstall with: "
                    "pip install -U 'python-telegram-bot>=21.11.1,<22'"
                )
            self._running = False
            raise

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        logger.info("Stopping Telegram channel...")
        self._running = False

        if self._outbound_task:
            self._outbound_task.cancel()
            try:
                await self._outbound_task
            except asyncio.CancelledError:
                pass

        for chat_id in list(self._typing_tasks.keys()):
            await self._stop_typing(chat_id)

        if self.app:
            try:
                if self.app.updater is not None:
                    await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except Exception as e:
                logger.error(f"Error during Telegram stop: {type(e).__name__}: {e}")

        self._save_ui_state()
        logger.info("Telegram channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message to Telegram with streaming, chunking, and button support."""
        metadata = msg.metadata or {}
        if not self.app:
            raise RuntimeError("Telegram app not initialized")

        try:
            chat_id = int(msg.chat_id)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid chat_id format: {msg.chat_id}")

        try:
            content = (msg.content or "").strip()
            if metadata.get("progress"):
                await self._send_progress_message(chat_id, msg.content, metadata)
                return

            buttons = self._build_inline_keyboard(metadata.get("telegram_buttons"))
            pending = metadata.get("telegram_pending_approval") or {}
            if pending:
                self._remember_pending_approval(str(chat_id), pending)

            if not content:
                raise ValueError("Skipping empty Telegram outbound message")
            await self._send_final_message(chat_id, content, metadata, buttons)
        except RetryAfter as e:
            logger.warning(f"Telegram rate-limited for {chat_id}, retrying after {e.retry_after}s")
            await asyncio.sleep(float(e.retry_after))
            await self.send(msg)
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            raise
        finally:
            if not metadata.get("progress"):
                await self._stop_typing(msg.chat_id)

    def _install_handlers(self) -> None:
        assert self.app is not None
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(CommandHandler("help", self._handle_help))
        self.app.add_handler(CommandHandler("status", self._handle_status))
        self.app.add_handler(CommandHandler("settings", self._handle_settings))
        self.app.add_handler(CommandHandler("memory", self._handle_memory))
        self.app.add_handler(CommandHandler("heartbeat", self._handle_heartbeat))
        self.app.add_handler(CommandHandler("approve", self._handle_approve))
        self.app.add_handler(CommandHandler("cancel", self._handle_cancel))
        self.app.add_handler(CommandHandler("stop", self._handle_stop))
        self.app.add_handler(CommandHandler("new", self._handle_new))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback_query))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.app.add_error_handler(self._handle_telegram_error)

    async def _handle_telegram_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Telegram handler error: {context.error}")

    @staticmethod
    def _reply_target(update: Update):
        return getattr(update, "effective_message", None) or getattr(update, "message", None)

    async def _register_telegram_commands(self) -> None:
        """Register Telegram command menu entries."""
        assert self.app is not None
        commands = [
            BotCommand("start", "Show the main menu"),
            BotCommand("help", "Show command and button help"),
            BotCommand("status", "Show runtime status for this chat"),
            BotCommand("settings", "Adjust Telegram streaming settings"),
            BotCommand("memory", "Ask the agent about memory/context"),
            BotCommand("heartbeat", "Ask for heartbeat status"),
            BotCommand("approve", "Approve the pending action"),
            BotCommand("cancel", "Cancel the pending action"),
            BotCommand("stop", "Stop live progress updates"),
            BotCommand("new", "Start a new conversation"),
        ]
        try:
            await self.app.bot.set_my_commands(commands)
            if MenuButtonCommands is not None:
                await self.app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        except Exception as e:
            logger.warning(f"Could not register Telegram commands/menu button: {e}")

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "there"
        self._ensure_chat_state(chat_id)
        await message.reply_text(
            self._render_welcome_text(user_name),
            reply_markup=self._default_reply_keyboard() if self._use_reply_keyboard else None,
        )
        await message.reply_text(
            self._render_help_card(),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
            disable_web_page_preview=True,
        )

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        await message.reply_text(
            self._render_help_card(),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
            disable_web_page_preview=True,
        )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        await message.reply_text(
            self._render_status_card(chat_id),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
            disable_web_page_preview=True,
        )

    async def _handle_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        await message.reply_text(
            self._render_settings_card(chat_id),
            parse_mode="HTML",
            reply_markup=self._settings_menu_markup(chat_id),
            disable_web_page_preview=True,
        )

    async def _handle_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id)
        await self._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content="Summarize the current memory and relevant context for this conversation.",
            metadata={"telegram_command": "memory"},
        )

    async def _handle_heartbeat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        await message.reply_text(
            self._render_heartbeat_card(chat_id),
            parse_mode="HTML",
            reply_markup=self._main_menu_markup(),
            disable_web_page_preview=True,
        )

    async def _handle_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        args = list(context.args or [])
        token = args[0] if args else self._latest_pending_token(chat_id)
        if not token:
            await message.reply_text("No pending action is waiting for approval in this chat.")
            return
        await self._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content=f"confirm {token}",
            metadata={"telegram_command": "approve", "approval_token": token},
        )
        await message.reply_text(f"Approval sent for token {token}.")

    async def _handle_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        await self._publish_agent_text(
            chat_id=chat_id,
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.first_name,
            content="cancel",
            metadata={"telegram_command": "cancel"},
        )
        self._forget_pending_approval(chat_id)
        await message.reply_text("Pending action cancelled.")

    async def _handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        state = self._ensure_chat_state(chat_id)
        state["active_stream_message_id"] = None
        state["last_stream_text"] = ""
        state["last_stream_update_ts"] = 0.0
        self._save_ui_state()
        await message.reply_text("Live progress updates stopped for this chat.")

    async def _handle_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = self._reply_target(update)
        if message is None:
            return
        chat_id = str(update.effective_chat.id)
        user_name = update.effective_user.first_name or "there"
        if self.agent:
            success = await self.agent.clear_conversation(self.name, chat_id)
            if success:
                await message.reply_text(
                    f"New conversation started for {user_name}.",
                    reply_markup=self._main_menu_markup(),
                )
                return
        await message.reply_text("New conversation started.", reply_markup=self._main_menu_markup())

    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        await query.answer()

        data = (query.data or "").strip()
        handled = await dispatch_callback_query(self, update, query, data)
        if not handled:
            await query.answer("Unsupported action.", show_alert=False)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = str(update.effective_chat.id)
        content = (update.message.text or "").strip()
        if await self._maybe_handle_text_menu_action(update, content):
            return
        msg = InboundMessage(
            channel=self.name,
            chat_id=chat_id,
            content=content,
            user_id=str(update.effective_user.id),
            metadata={
                "user_name": update.effective_user.first_name,
                "username": update.effective_user.username,
            },
        )
        await self._start_typing(chat_id)
        try:
            await self.bus.publish_inbound(msg)
        except Exception:
            await self._stop_typing(chat_id)
            raise

    async def _maybe_handle_text_menu_action(self, update: Update, content: str) -> bool:
        action = resolve_text_menu_action(content)
        if not action:
            return False
        return await dispatch_text_menu_action(self, update, action)

    async def _publish_agent_text(
        self,
        *,
        chat_id: str,
        user_id: str,
        user_name: Optional[str],
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        await self._start_typing(chat_id)
        try:
            await self.bus.publish_inbound(
                InboundMessage(
                    channel=self.name,
                    chat_id=chat_id,
                    content=content,
                    user_id=user_id,
                    metadata={
                        "user_name": user_name,
                        **(metadata or {}),
                    },
                )
            )
        except Exception:
            await self._stop_typing(chat_id)
            raise

    async def _send_progress_message(self, chat_id: int, content: str, metadata: dict) -> None:
        state = self._ensure_chat_state(str(chat_id))
        mode = state.get("stream_mode", self._stream_mode_default)
        if mode == "off":
            return

        event_type = str(metadata.get("progress_event", "") or "")
        detail = str(metadata.get("progress_detail", "") or "")
        text = self._render_progress_text(mode, event_type, content, detail)
        if not text or text == state.get("last_stream_text"):
            return

        now = time.time()
        active_message_id = state.get("active_stream_message_id")
        trusted_html = mode == "verbose_debug"
        if active_message_id and now - float(state.get("last_stream_update_ts", 0.0) or 0.0) < self._stream_update_interval:
            if event_type not in {"tool_failed", "completed"}:
                return

        if active_message_id:
            try:
                await self._edit_message(
                    chat_id=chat_id,
                    message_id=int(active_message_id),
                    text=text,
                    reply_markup=None,
                    trusted_html=trusted_html,
                )
            except Exception:
                sent = await self._send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=None,
                    trusted_html=trusted_html,
                )
                state["active_stream_message_id"] = getattr(sent, "message_id", None)
                self._save_ui_state()
        else:
            sent = await self._send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=None,
                trusted_html=trusted_html,
            )
            state["active_stream_message_id"] = getattr(sent, "message_id", None)
            self._save_ui_state()

        state["last_stream_text"] = text
        state["last_stream_update_ts"] = now

    async def _send_final_message(
        self,
        chat_id: int,
        content: str,
        metadata: dict,
        buttons: Optional[InlineKeyboardMarkup],
    ) -> None:
        state = self._ensure_chat_state(str(chat_id))
        chunks = self._chunk_text(content or "")
        active_message_id = state.get("active_stream_message_id")

        if active_message_id and chunks:
            first_chunk = chunks.pop(0)
            try:
                await self._edit_message(
                    chat_id=chat_id,
                    message_id=int(active_message_id),
                    text=first_chunk,
                    reply_markup=buttons,
                    disable_preview=metadata.get("telegram_disable_preview", self._disable_web_page_preview),
                )
            except Exception:
                sent = await self._send_message(
                    chat_id=chat_id,
                    text=first_chunk,
                    reply_markup=buttons,
                    disable_preview=metadata.get("telegram_disable_preview", self._disable_web_page_preview),
                )
                active_message_id = getattr(sent, "message_id", None)
            for chunk in chunks:
                sent = await self._send_message(
                    chat_id=chat_id,
                    text=chunk,
                    reply_markup=None,
                    disable_preview=metadata.get("telegram_disable_preview", self._disable_web_page_preview),
                )
                active_message_id = getattr(sent, "message_id", active_message_id)
        else:
            for index, chunk in enumerate(chunks or [""]):
                sent = await self._send_message(
                    chat_id=chat_id,
                    text=chunk,
                    reply_markup=buttons if index == 0 else None,
                    disable_preview=metadata.get("telegram_disable_preview", self._disable_web_page_preview),
                )
                active_message_id = getattr(sent, "message_id", active_message_id)

        state["active_stream_message_id"] = None
        state["last_stream_text"] = ""
        state["last_stream_update_ts"] = 0.0
        if active_message_id is not None:
            state["last_message_id"] = active_message_id
        self._save_ui_state()

    async def _send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: Optional[Any],
        disable_preview: bool = True,
        trusted_html: bool = False,
    ):
        html_text = _prepare_html_text(text, trusted_html=trusted_html)
        try:
            return await self.app.bot.send_message(
                chat_id=chat_id,
                text=html_text,
                parse_mode="HTML",
                disable_web_page_preview=disable_preview,
                reply_markup=reply_markup,
            )
        except BadRequest:
            return await self.app.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=None,
                disable_web_page_preview=disable_preview,
                reply_markup=reply_markup,
            )

    async def _edit_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: Optional[Any],
        disable_preview: bool = True,
        trusted_html: bool = False,
    ) -> None:
        html_text = _prepare_html_text(text, trusted_html=trusted_html)
        try:
            await self.app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=html_text,
                parse_mode="HTML",
                disable_web_page_preview=disable_preview,
                reply_markup=reply_markup,
            )
        except BadRequest:
            await self.app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=None,
                disable_web_page_preview=disable_preview,
                reply_markup=reply_markup,
            )

    async def _edit_callback_message(
        self,
        query,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup],
        trusted_html: bool = True,
    ) -> None:
        try:
            await query.edit_message_text(
                text=_prepare_html_text(text, trusted_html=trusted_html),
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except BadRequest:
            try:
                await query.edit_message_text(
                    text=text,
                    parse_mode=None,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.debug(f"Could not edit callback message: {e}")

    def _render_progress_text(self, mode: str, event_type: str, content: str, detail: str) -> str:
        base = content.strip()
        if mode == "verbose_debug" and detail:
            return f"{base}\n<code>{escape(detail)}</code>"
        if mode == "progress":
            return base
        return ""

    def _render_welcome_text(self, user_name: str) -> str:
        return (
            f"Hello {user_name}. I am Clawlet on Telegram.\n\n"
            "Use the command menu or the inline controls below to inspect status, change streaming mode, "
            "approve actions, and start new work."
        )

    def _render_help_card(self) -> str:
        return (
            "<b>Telegram controls</b>\n"
            "Use the Telegram command menu, the reply keyboard, or the inline buttons below.\n\n"
            "<b>Streaming</b>\n"
            "Progress mode edits one live message while the agent is working.\n"
            "Verbose debug adds tool-level details. Off only sends the final answer."
        )

    def _render_status_card(self, chat_id: str) -> str:
        state = self._ensure_chat_state(chat_id)
        pending_count = len((state.get("pending_approvals") or {}))
        runtime = self.agent.get_runtime_status(self.name, chat_id) if self.agent else {}
        return (
            "<b>Telegram status</b>\n"
            f"Stream mode: <code>{state.get('stream_mode', self._stream_mode_default)}</code>\n"
            f"Active stream message: <code>{state.get('active_stream_message_id') or 'none'}</code>\n"
            f"Pending approvals: <code>{pending_count}</code>\n"
            f"Session: <code>{runtime.get('session_id', 'n/a')}</code>\n"
            f"Messages in memory: <code>{runtime.get('history_messages', 0)}</code>\n"
            f"Current run: <code>{runtime.get('current_run_id') or 'idle'}</code>"
        )

    def _render_settings_card(self, chat_id: str) -> str:
        state = self._ensure_chat_state(chat_id)
        return (
            "<b>Telegram settings</b>\n"
            f"Current stream mode: <code>{state.get('stream_mode', self._stream_mode_default)}</code>\n"
            f"Edit throttle: <code>{self._stream_update_interval:.1f}s</code>\n"
            f"Link previews: <code>{'off' if self._disable_web_page_preview else 'on'}</code>"
        )

    def _render_heartbeat_card(self, chat_id: str) -> str:
        enabled = bool(self._heartbeat_config.get("enabled", False))
        interval = int(self._heartbeat_config.get("interval_minutes", 30) or 30)
        proactive_enabled = bool(self._heartbeat_config.get("proactive_enabled", False))
        target = str(self._heartbeat_config.get("target", "last") or "last")
        ack_max_chars = int(self._heartbeat_config.get("ack_max_chars", 24) or 24)
        quiet_hours = self._format_quiet_hours()
        route = self.agent.get_last_route() if self.agent else None
        if route:
            if isinstance(route, dict):
                channel = str(route.get("channel") or "")
                route_chat_id = str(route.get("chat_id") or "")
            else:
                channel = str(getattr(route, "channel", "") or "")
                route_chat_id = str(getattr(route, "chat_id", "") or "")
            route_text = f"<code>{escape(channel)}/{escape(route_chat_id)}</code>"
        else:
            route_text = "<code>scheduler/main</code>"
        route_label = "Last route" if target == "last" else "Target route"
        if target == "last" and not route:
            route_label = "Fallback route"

        return (
            "<b>Heartbeat status</b>\n"
            f"Enabled: <code>{'yes' if enabled else 'no'}</code>\n"
            f"Interval: <code>{interval}m</code>\n"
            f"Quiet hours: <code>{quiet_hours}</code>\n"
            f"Target: <code>{escape(target)}</code>\n"
            f"{route_label}: {route_text}\n"
            f"Proactive queue: <code>{'on' if proactive_enabled else 'off'}</code>\n"
            f"Ack limit: <code>{ack_max_chars}</code>"
        )

    def _format_quiet_hours(self) -> str:
        start = int(self._heartbeat_config.get("quiet_hours_start", 0) or 0)
        end = int(self._heartbeat_config.get("quiet_hours_end", 0) or 0)
        if start == end:
            return "disabled"
        return f"{start:02d}:00-{end:02d}:00 UTC"

    def _default_reply_keyboard(self) -> ReplyKeyboardMarkup:
        return default_reply_keyboard()

    def _main_menu_markup(self) -> InlineKeyboardMarkup:
        return main_menu_markup()

    def _settings_menu_markup(self, chat_id: str) -> InlineKeyboardMarkup:
        current = self._ensure_chat_state(chat_id).get("stream_mode", self._stream_mode_default)
        return settings_menu_markup(current)

    def _build_inline_keyboard(self, button_rows: Any) -> Optional[InlineKeyboardMarkup]:
        return build_inline_keyboard(button_rows)

    def _chunk_text(self, text: str) -> list[str]:
        if not text:
            return [""]
        if len(text) <= TELEGRAM_SAFE_HTML_CHUNK:
            return [text]

        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= TELEGRAM_SAFE_HTML_CHUNK:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, TELEGRAM_SAFE_HTML_CHUNK)
            if split_at <= 0:
                split_at = TELEGRAM_SAFE_HTML_CHUNK
            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip("\n")
        return chunks

    def _resolve_ui_state_path(self) -> Path:
        if self.agent is not None and getattr(self.agent, "workspace", None) is not None:
            return Path(self.agent.workspace) / ".telegram_ui_state.json"
        return get_default_workspace_path() / ".telegram_ui_state.json"

    def _load_ui_state(self) -> dict[str, dict[str, Any]]:
        try:
            if not self._ui_state_path.exists():
                return {}
            payload = json.loads(self._ui_state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception as e:
            logger.warning(f"Could not load Telegram UI state: {e}")
            return {}

    def _save_ui_state(self) -> None:
        try:
            self._ui_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._ui_state_path.write_text(json.dumps(self._chat_state, indent=2, sort_keys=True), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not persist Telegram UI state: {e}")

    def _ensure_chat_state(self, chat_id: str) -> dict[str, Any]:
        state = self._chat_state.setdefault(
            chat_id,
            {
                "stream_mode": self._stream_mode_default,
                "active_stream_message_id": None,
                "last_stream_text": "",
                "last_stream_update_ts": 0.0,
                "last_message_id": None,
                "pending_approvals": {},
            },
        )
        if state.get("stream_mode") not in STREAM_MODES:
            state["stream_mode"] = self._stream_mode_default
        state.setdefault("pending_approvals", {})
        return state

    def _normalize_stream_mode(self, value: Any) -> str:
        fallback = getattr(self, "_stream_mode_default", "progress")
        mode = str(value or fallback).strip().lower()
        return mode if mode in STREAM_MODES else "progress"

    def _remember_pending_approval(self, chat_id: str, payload: dict) -> None:
        token = str(payload.get("token", "") or "").strip()
        if not token:
            return
        state = self._ensure_chat_state(chat_id)
        state["pending_approvals"][token] = {
            "reason": str(payload.get("reason", "") or ""),
            "tool_name": str(payload.get("tool_name", "") or ""),
            "details": str(payload.get("details", "") or ""),
        }
        self._save_ui_state()

    def _forget_pending_approval(self, chat_id: str, token: Optional[str] = None) -> None:
        state = self._ensure_chat_state(chat_id)
        pending = state.get("pending_approvals", {})
        if token:
            pending.pop(token, None)
        else:
            pending.clear()
        self._save_ui_state()

    def _latest_pending_token(self, chat_id: str) -> str:
        pending = self._ensure_chat_state(chat_id).get("pending_approvals", {})
        if not pending:
            agent_pending = self.agent.peek_pending_confirmation(self.name, chat_id) if self.agent else None
            return str((agent_pending or {}).get("token", "") or "")
        return next(reversed(pending.keys()))

    def _pending_approval_details(self, chat_id: str, token: str) -> str:
        pending = self._ensure_chat_state(chat_id).get("pending_approvals", {})
        details = (pending.get(token) or {}).get("details", "")
        if details:
            return details
        if self.agent:
            payload = self.agent.peek_pending_confirmation(self.name, chat_id) or {}
            if payload.get("token") == token:
                return json.dumps(payload.get("arguments", {}), indent=2, sort_keys=True)
        return ""

    async def _start_typing(self, chat_id: str) -> None:
        self._typing_refcounts[chat_id] += 1
        if chat_id in self._typing_tasks:
            return
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_keepalive_loop(chat_id))

    async def _stop_typing(self, chat_id: str) -> None:
        count = self._typing_refcounts.get(chat_id, 0)
        if count <= 0:
            return
        count -= 1
        if count > 0:
            self._typing_refcounts[chat_id] = count
            return
        self._typing_refcounts.pop(chat_id, None)
        task = self._typing_tasks.pop(chat_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _typing_keepalive_loop(self, chat_id: str) -> None:
        try:
            while self._running and self._typing_refcounts.get(chat_id, 0) > 0:
                try:
                    await self.app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                except Exception as e:
                    logger.debug(f"Could not send typing action for {chat_id}: {e}")
                await asyncio.sleep(4.0)
        except asyncio.CancelledError:
            raise
