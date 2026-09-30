"""Действия панели (ReplyKeyboard): slow-mode, мут, удаление, добавление, CSV, админы."""
from __future__ import annotations

import csv
import io

from telegram import Update
from telegram.ext import ContextTypes

import database
from handlers.admin_panel import (
    show_admin_pick,
    show_admins,
    show_card,
    show_members,
)
from handlers.common import (
    BTN_BACK,
    BTN_CUSTOM,
    BTN_CUSTOM_SHORT,
    BTN_DELETE_YES,
    BTN_MEMBERS,
    MUTE_PRESETS,
    SLOW_PRESETS,
    check_admin,
    fmt_until,
    interval_label,
    kb,
    send_screen,
)


def _sel(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    return context.user_data.get("selected")


# ---------- медленный режим ----------

async def ask_slow(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "slow_menu"
    await send_screen(
        message, context,
        "<b>Медленный режим</b>\nВыбери интервал:",
        kb(["Раз в 30 мин", "Раз в час"],
           ["Раз в 3 часа", "Раз в день"],
           [BTN_CUSTOM],
           [BTN_BACK]),
    )


async def apply_slow_preset(message, context: ContextTypes.DEFAULT_TYPE,
                            minutes: int) -> None:
    uid = _sel(context)
    if uid is None:
        return
    await database.set_restriction(uid, minutes)
    m = await database.get_member(uid)
    name = (m["full_name"] if m else str(uid)) or str(uid)
    await message.reply_text(
        f"<b>{name}</b> — 1 сообщение {interval_label(minutes)}",
        parse_mode="HTML")
    await show_card(message, context, uid)


async def ask_slow_custom(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "await_slow"
    await send_screen(message, context,
                      "Введи интервал в <b>минутах</b> числом:",
                      kb([BTN_BACK]))


async def save_slow_custom(message, context: ContextTypes.DEFAULT_TYPE,
                           text: str) -> None:
    uid = _sel(context)
    if uid is None:
        return
    try:
        minutes = int(text.strip())
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text(
            "Нужно положительное число минут. Попробуй ещё раз:")
        return
    await database.set_restriction(uid, minutes)
    m = await database.get_member(uid)
    name = (m["full_name"] if m else str(uid)) or str(uid)
    await message.reply_text(
        f"{name} — 1 сообщение {interval_label(minutes)}")
    await show_card(message, context, uid)


async def remove_slow(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sel(context)
    if uid is None:
        return
    await database.remove_restriction(uid)
    await message.reply_text("Ограничение снято.")
    await show_card(message, context, uid)


# ---------- мут ----------

async def ask_mute(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "mute_menu"
    await send_screen(
        message, context,
        "<b>Мут</b>\nНа сколько замьютить?",
        kb(["1 час", "3 часа"],
           ["1 день", BTN_CUSTOM_SHORT],
           [BTN_BACK]),
    )


async def apply_mute_preset(message, context: ContextTypes.DEFAULT_TYPE,
                            minutes: int) -> None:
    uid = _sel(context)
    if uid is None:
        return
    until = await database.set_mute(uid, minutes)
    m = await database.get_member(uid)
    name = (m["full_name"] if m else str(uid)) or str(uid)
    await message.reply_text(f"{name} замьючен до {fmt_until(until)}")
    await show_card(message, context, uid)


async def ask_mute_custom(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "await_mute"
    await send_screen(message, context,
                      "Введи длительность мута в <b>минутах</b> числом:",
                      kb([BTN_BACK]))


async def save_mute_custom(message, context: ContextTypes.DEFAULT_TYPE,
                           text: str) -> None:
    uid = _sel(context)
    if uid is None:
        return
    try:
        minutes = int(text.strip())
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text(
            "Нужно положительное число минут. Попробуй ещё раз:")
        return
    until = await database.set_mute(uid, minutes)
    m = await database.get_member(uid)
    name = (m["full_name"] if m else str(uid)) or str(uid)
    await message.reply_text(f"{name} замьючен до {fmt_until(until)}")
    await show_card(message, context, uid)


async def remove_mute(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sel(context)
    if uid is None:
        return
    await database.remove_mute(uid)
    await message.reply_text("Мут снят.")
    await show_card(message, context, uid)


# ---------- сброс счётчика ----------

async def reset_stats(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sel(context)
    if uid is None:
        return
    await database.clear_violations(uid)
    await message.reply_text("Счётчик срабатываний сброшен.")
    await show_card(message, context, uid)


# ---------- удаление ----------

async def ask_delete(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sel(context)
    m = await database.get_member(uid) if uid else None
    name = ((m["full_name"] if m else None) or str(uid))
    context.user_data["screen"] = "del_confirm"
    await send_screen(message, context,
                      f"Удалить <b>{name}</b> из списка?",
                      kb([BTN_DELETE_YES], [BTN_BACK]))


async def apply_delete(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sel(context)
    if uid is None:
        return
    await database.delete_member(uid)
    context.user_data.pop("selected", None)
    await message.reply_text("Участник удалён.")
    back = context.user_data.get("return_to", "members")
    if back == "restricted":
        from handlers.admin_panel import show_restricted
        await show_restricted(message, context)
    else:
        await show_members(message, context,
                           context.user_data.get("page", 0))


# ---------- добавление вручную ----------

async def ask_add_id(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "await_add_id"
    await send_screen(message, context, "Введи <b>user_id</b> числом:",
                      kb([BTN_BACK]))


async def save_add_id(message, context: ContextTypes.DEFAULT_TYPE,
                      text: str) -> None:
    try:
        uid = int(text.strip())
    except ValueError:
        await message.reply_text("user_id — это число. Попробуй ещё раз:")
        return
    if await database.get_member(uid) is not None:
        await message.reply_text(
            "Такой участник уже есть. Введи другой user_id:")
        return
    context.user_data["add_id"] = uid
    context.user_data["screen"] = "await_add_name"
    await message.reply_text("Введи <b>имя</b>:", parse_mode="HTML")


async def save_add_name(message, context: ContextTypes.DEFAULT_TYPE,
                        text: str) -> None:
    uid = context.user_data.pop("add_id", None)
    if uid is None:
        context.user_data["screen"] = "await_add_id"
        await message.reply_text("Сначала введи user_id числом:")
        return
    name = (text or "").strip()
    if not name:
        context.user_data["add_id"] = uid
        await message.reply_text("Имя не может быть пустым:")
        return
    ok = await database.add_member(uid, name)
    await message.reply_text(
        f"{name} добавлен" if ok else "Такой участник уже есть.")
    await show_members(message, context, 0)


# ---------- CSV ----------

async def csv_hint(message, context: ContextTypes.DEFAULT_TYPE) -> None:
    await message.reply_html(
        "Пришли <b>CSV-файл</b> в личку.\nФормат строк:\n"
        "<code>123456789,Иван Иванов\n"
        "987654321,Пётр Петров,@petrov</code>")


async def handle_csv(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_admin(update):
        return
    doc = update.message.document
    if doc is None or not (doc.file_name or "").lower().endswith(
            (".csv", ".txt")):
        return
    f = await doc.get_file()
    buf = io.BytesIO()
    await f.download_to_memory(buf)
    text = buf.getvalue().decode("utf-8-sig", errors="replace")
    added = 0
    skipped = 0
    for row in csv.reader(io.StringIO(text)):
        if not row or len(row) < 2:
            skipped += 1
            continue
        try:
            uid = int(row[0].strip())
        except ValueError:
            skipped += 1
            continue
        name = row[1].strip()
        username = (row[2].strip().lstrip("@")
                    if len(row) > 2 and row[2].strip() else None)
        if not name:
            skipped += 1
            continue
        if await database.add_member(uid, name, username):
            added += 1
        else:
            skipped += 1
    msg = f"Добавлено: {added}"
    if skipped:
        msg += f"\nПропущено: {skipped} (дубликаты/ошибки)"
    await update.message.reply_text(msg)
    await show_members(update.message, context, 0)


# ---------- админы ----------

async def admin_pick_select(message, context: ContextTypes.DEFAULT_TYPE,
                            uid: int) -> None:
    m = await database.get_member(uid)
    await database.add_admin(
        uid,
        username=(m["username"] if m else None),
        full_name=(m["full_name"] if m else None),
    )
    name = ((m["full_name"] if m else None) or str(uid))
    await message.reply_text(f"{name} теперь админ.")
    await show_admins(message, context)


async def admin_ask_delete(message,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["screen"] = "admin_del_confirm"
    await send_screen(message, context,
                      "Удалить из админов?",
                      kb([BTN_DELETE_YES], [BTN_BACK]))


async def admin_apply_delete(message,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
    import config
    uid = _sel(context)
    if uid is None:
        return
    if uid == config.SUPER_ADMIN_ID:
        await message.reply_text("Суперадмина удалить нельзя.")
        await show_admins(message, context)
        return
    await database.remove_admin(uid)
    context.user_data.pop("selected", None)
    await message.reply_text("Админ удалён.")
    await show_admins(message, context)
