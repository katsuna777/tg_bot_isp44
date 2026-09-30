"""Экраны панели (ReplyKeyboard): главное меню, участники, ограниченные, админы."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

import config
import database
from handlers.common import (
    BTN_ADD,
    BTN_ADMIN_ADD,
    BTN_ADMINS,
    BTN_BACK,
    BTN_CSV,
    BTN_DELETE,
    BTN_MEMBERS,
    BTN_MUTE,
    BTN_MUTE_EDIT,
    BTN_NEXT,
    BTN_PREV,
    BTN_RESTRICTED,
    BTN_SLOW,
    BTN_SLOW_EDIT,
    BTN_UNMUTE,
    BTN_UNSLOW,
    display_name,
    fmt_created,
    fmt_until,
    interval_label,
    is_super,
    kb,
    main_menu_kb,
    send_screen,
)

PAGE_SIZE = config.PAGE_SIZE


# ---------- главное меню ----------

async def show_main(message, context: ContextTypes.DEFAULT_TYPE,
                    user_id: int) -> None:
    context.user_data.clear()
    context.user_data["screen"] = "main"
    await send_screen(
        message, context,
        "<b>Панель управления</b>\nВыбери раздел кнопками ниже.",
        main_menu_kb(await is_super(user_id)),
    )


async def cmd_start(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.common import check_admin
    if update.effective_chat is None or update.effective_chat.type != "private":
        return
    if not await check_admin(update):
        return  # чужой /start — игнор
    await show_main(update.message, context, update.effective_user.id)


# ---------- участники ----------

async def show_members(message, context: ContextTypes.DEFAULT_TYPE,
                       page: int = 0) -> None:
    total = await database.count_members()
    members = await database.get_members(
        limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    context.user_data["screen"] = "members"
    context.user_data["page"] = page
    context.user_data["list_ids"] = [m["user_id"] for m in members]

    if not total:
        text = "<b>Участники</b>\n\nПока никого нет. Добавь вручную или загрузи CSV."
    else:
        lines = [f"<b>Участники</b> · {total}",
                 "Нажми <b>номер</b>, чтобы открыть карточку.\n"]
        base = page * PAGE_SIZE
        for i, m in enumerate(members, start=base + 1):
            lines.append(
                f"{i}. {display_name(m['full_name'], m['username'], m['user_id'])}")
        pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        if pages > 1:
            lines.append(f"\nСтр. {page + 1}/{pages}")
        text = "\n".join(lines)

    num_row = [str(i) for i in
               range(page * PAGE_SIZE + 1,
                     page * PAGE_SIZE + len(members) + 1)]
    rows: list[list[str]] = []
    for j in range(0, len(num_row), 5):
        rows.append(num_row[j:j + 5])
    nav: list[str] = []
    if page > 0:
        nav.append(BTN_PREV)
    if (page + 1) * PAGE_SIZE < total:
        nav.append(BTN_NEXT)
    if nav:
        rows.append(nav)
    rows.append([BTN_ADD, BTN_CSV])
    rows.append([BTN_BACK])
    await send_screen(message, context, text, kb(*rows))


# ---------- карточка участника ----------

async def show_card(message, context: ContextTypes.DEFAULT_TYPE,
                    user_id: int) -> None:
    m = await database.get_member(user_id)
    if m is None:
        await show_members(message, context,
                           context.user_data.get("page", 0))
        return
    mute = await database.get_mute(user_id)
    restr = await database.get_restriction(user_id)
    context.user_data["screen"] = "card"
    context.user_data["selected"] = user_id

    uname = f" · @{m['username'].lstrip('@')}" if m["username"] else ""
    header = (f"<b>{m['full_name'] or '—'}</b>\n"
              f"<code>{m['user_id']}</code>{uname}")
    if mute:
        status = f"<b>Статус:</b> мут до {fmt_until(mute['until'])}"
        rows = [[BTN_MUTE_EDIT, BTN_UNMUTE],
                [BTN_SLOW, BTN_DELETE],
                [BTN_BACK]]
    elif restr:
        status = (f"<b>Статус:</b> {interval_label(restr['interval_minutes'])}"
                  + (f"\nс {fmt_created(restr['created_at'])}"
                     if restr["created_at"] else ""))
        rows = [[BTN_SLOW_EDIT, BTN_UNSLOW],
                [BTN_MUTE, BTN_DELETE],
                [BTN_BACK]]
    else:
        status = "<b>Статус:</b> без ограничений"
        rows = [[BTN_SLOW, BTN_MUTE],
                [BTN_DELETE],
                [BTN_BACK]]
    await send_screen(message, context, f"{header}\n\n{status}", kb(*rows))


# ---------- ограниченные ----------

async def show_restricted(message,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    slow, mutes = await database.get_restricted()
    context.user_data["screen"] = "restricted"
    items: list[tuple[int, str]] = []
    for r in slow:
        items.append((r["user_id"],
                      f"{r['full_name']} — {interval_label(r['interval_minutes'])}"))
    for r in mutes:
        items.append((r["user_id"],
                      f"{r['full_name']} — мут до {fmt_until(r['until'])}"))
    context.user_data["list_ids"] = [uid for uid, _ in items]

    if not items:
        await send_screen(message, context,
                          "<b>Ограниченные</b>\n\nНикого нет — все пишут свободно.",
                          kb([BTN_BACK]))
        return
    lines = ["<b>Ограниченные</b>",
             "Нажми <b>номер</b>, чтобы открыть карточку.\n"]
    for i, (_, label) in enumerate(items, start=1):
        lines.append(f"{i}. {label}")
    num_row = [str(i) for i in range(1, len(items) + 1)]
    rows: list[list[str]] = []
    for j in range(0, len(num_row), 5):
        rows.append(num_row[j:j + 5])
    rows.append([BTN_BACK])
    await send_screen(message, context, "\n".join(lines), kb(*rows))


# ---------- админы ----------

async def show_admins(message,
                      context: ContextTypes.DEFAULT_TYPE) -> None:
    admins = await database.get_admins()
    context.user_data["screen"] = "admins"
    others = [a for a in admins if a["user_id"] != config.SUPER_ADMIN_ID]
    context.user_data["list_ids"] = [a["user_id"] for a in others]

    lines = ["<b>Администраторы</b>", "", "Ты (суперадмин)"]
    for i, a in enumerate(others, start=1):
        lines.append(
            f"{i}. {display_name(a['full_name'], a['username'], a['user_id'])}")
    if not others:
        lines.append("\nДругих админов пока нет.")
    else:
        lines.append("\nНажми <b>номер</b>, чтобы удалить админа.")

    rows: list[list[str]] = []
    nums = [str(i) for i in range(1, len(others) + 1)]
    for j in range(0, len(nums), 5):
        rows.append(nums[j:j + 5])
    rows.append([BTN_ADMIN_ADD])
    rows.append([BTN_BACK])
    await send_screen(message, context, "\n".join(lines), kb(*rows))


async def show_admin_pick(message, context: ContextTypes.DEFAULT_TYPE,
                          page: int = 0) -> None:
    total = await database.count_members()
    members = await database.get_members(
        limit=PAGE_SIZE, offset=page * PAGE_SIZE)
    context.user_data["screen"] = "admin_pick"
    context.user_data["page"] = page
    context.user_data["list_ids"] = [m["user_id"] for m in members]

    lines = ["<b>Новый админ</b>", "Выбери участника кнопкой-номером.\n"]
    for i, m in enumerate(members, start=page * PAGE_SIZE + 1):
        lines.append(
            f"{i}. {display_name(m['full_name'], m['username'], m['user_id'])}")
    if not members:
        lines = ["<b>Новый админ</b>", "", "Сначала добавь участников."]

    num_row = [str(i) for i in
               range(page * PAGE_SIZE + 1,
                     page * PAGE_SIZE + len(members) + 1)]
    rows: list[list[str]] = []
    for j in range(0, len(num_row), 5):
        rows.append(num_row[j:j + 5])
    nav: list[str] = []
    if page > 0:
        nav.append(BTN_PREV)
    if (page + 1) * PAGE_SIZE < total:
        nav.append(BTN_NEXT)
    if nav:
        rows.append(nav)
    rows.append([BTN_BACK])
    await send_screen(message, context, "\n".join(lines), kb(*rows))


async def show_admin_card(message, context: ContextTypes.DEFAULT_TYPE,
                          user_id: int) -> None:
    context.user_data["screen"] = "admin_card"
    context.user_data["selected"] = user_id
    await send_screen(
        message, context,
        f"<b>Админ</b>\n<code>{user_id}</code>\n\nУдалить из админов?",
        kb([BTN_DELETE], [BTN_BACK]),
    )
