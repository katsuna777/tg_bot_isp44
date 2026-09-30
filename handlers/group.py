"""Молчаливая модерация группы: только удаление, никаких ответов."""
from __future__ import annotations

import time

from telegram import Update
from telegram.ext import ContextTypes

import config
import database


async def moderate_group(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if msg is None or user is None or chat is None:
        return
    if chat.id != config.CHAT_ID:
        return
    if user.is_bot:
        return
    if await database.is_admin(user.id):
        return

    # 1. Мут
    mute = await database.get_mute(user.id, chat.id)
    if mute is not None:
        try:
            await msg.delete()
        except Exception:
            pass
        return

    # 2. Медленный режим
    restr = await database.get_restriction(user.id, chat.id)
    if restr is None:
        return
    now = int(time.time())
    last = restr["last_message_at"]
    interval = int(restr["interval_minutes"]) * 60
    if last is not None and now - int(last) < interval:
        try:
            await msg.delete()
        except Exception:
            pass
        return
    await database.touch_last_message(user.id, chat.id)
