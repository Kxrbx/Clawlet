"""Telegram UI rendering helpers for menus and keyboards."""

from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def default_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Status", "Settings"],
            ["Memory", "Heartbeat"],
            ["Approve", "Cancel"],
            ["New conversation", "Stop updates"],
        ],
        resize_keyboard=True,
    )


def main_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Status", callback_data="action:status"),
                InlineKeyboardButton("Settings", callback_data="menu:settings"),
            ],
            [
                InlineKeyboardButton("Memory", callback_data="action:memory"),
                InlineKeyboardButton("Heartbeat", callback_data="action:heartbeat"),
            ],
            [
                InlineKeyboardButton("New conversation", callback_data="action:new"),
            ],
        ]
    )


def settings_menu_markup(current: str) -> InlineKeyboardMarkup:
    def _label(mode: str) -> str:
        return f"{'• ' if current == mode else ''}{mode}"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(_label("off"), callback_data="settings:stream_mode:off"),
                InlineKeyboardButton(_label("progress"), callback_data="settings:stream_mode:progress"),
                InlineKeyboardButton(_label("verbose_debug"), callback_data="settings:stream_mode:verbose_debug"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="menu:main"),
            ],
        ]
    )


def build_inline_keyboard(button_rows: Any) -> InlineKeyboardMarkup | None:
    if not button_rows:
        return None
    rows = []
    for row in button_rows:
        buttons = []
        for button in row:
            text = str(button.get("text", "") or "").strip()
            if not text:
                continue
            if button.get("url"):
                buttons.append(InlineKeyboardButton(text, url=str(button["url"])))
                continue
            callback_data = str(button.get("callback_data", "") or "").strip()
            if callback_data:
                buttons.append(InlineKeyboardButton(text, callback_data=callback_data))
        if buttons:
            rows.append(buttons)
    return InlineKeyboardMarkup(rows) if rows else None
