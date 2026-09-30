"""Точка входа. Личка — ReplyKeyboard-панель, группа — молчаливое удаление."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import database
from handlers.admin_panel import (
    cmd_start,
    show_admin_card,
    show_admin_pick,
    show_admins,
    show_card,
    show_main,
    show_members,
    show_restricted,
)
from handlers.common import (
    BTN_ADD,
    BTN_ADMIN_ADD,
    BTN_ADMINS,
    BTN_BACK,
    BTN_CSV,
    BTN_CUSTOM,
    BTN_CUSTOM_SHORT,
    BTN_DELETE,
    BTN_DELETE_YES,
    BTN_MEMBERS,
    BTN_MUTE,
    BTN_MUTE_EDIT,
    BTN_NEXT,
    BTN_PREV,
    BTN_RESET,
    BTN_RESTRICTED,
    BTN_SLOW,
    BTN_SLOW_EDIT,
    BTN_UNMUTE,
    BTN_UNSLOW,
    MUTE_PRESETS,
    SLOW_PRESETS,
    check_admin,
    is_super,
)
from handlers.group import moderate_group
from handlers.restrictions import (
    admin_apply_delete,
    admin_ask_delete,
    admin_pick_select,
    apply_delete,
    apply_mute_preset,
    apply_slow_preset,
    ask_add_id,
    ask_delete,
    ask_mute,
    ask_mute_custom,
    ask_slow,
    ask_slow_custom,
    csv_hint,
    handle_csv,
    remove_mute,
    remove_slow,
    reset_stats,
    save_add_id,
    save_add_name,
    save_mute_custom,
    save_slow_custom,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
# глушим шум поллинга, чтобы в journalctl были видны только наши строки
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("college_bot")


def _pick_number(text: str, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    text = (text or "").strip()
    if not text.isdigit():
        return None
    idx = int(text) - 1
    ids = context.user_data.get("list_ids") or []
    if 0 <= idx < len(ids):
        return ids[idx]
    return None


async def on_text(update: Update,
                  context: ContextTypes.DEFAULT_TYPE) -> None:
    """Единый роутер панели по нижней клавиатуре."""
    msg = update.message
    if msg is None or update.effective_chat is None:
        return
    if update.effective_chat.type != "private":
        return
    if not await check_admin(update):
        return  # чужих молча игнорируем
    text = (msg.text or "").strip()
    if not text:
        return
    user_id = update.effective_user.id
    screen = context.user_data.get("screen", "main")
    me_super = await is_super(user_id)

    # --- глобальные разделы (работают с любого экрана) ---
    if text == BTN_MEMBERS:
        context.user_data["return_to"] = "members"
        await show_members(msg, context, 0)
        return
    if text == BTN_RESTRICTED:
        context.user_data["return_to"] = "restricted"
        await show_restricted(msg, context)
        return
    if text == BTN_ADMINS:
        if not me_super:
            await msg.reply_text("Раздел только для суперадмина.")
            return
        await show_admins(msg, context)
        return

    # --- пресетные интервалы (работают с экранов slow/mute) ---
    if text in SLOW_PRESETS and screen in ("slow_menu", "card",
                                           "card_after", "await_slow"):
        await apply_slow_preset(msg, context, SLOW_PRESETS[text])
        return
    if text in MUTE_PRESETS and screen in ("mute_menu", "card",
                                           "card_after", "await_mute"):
        await apply_mute_preset(msg, context, MUTE_PRESETS[text])
        return

    # --- поэкранная логика ---
    if screen == "main":
        await show_main(msg, context, user_id)
        return

    if screen == "members":
        if text == BTN_ADD:
            await ask_add_id(msg, context)
            return
        if text == BTN_CSV:
            await csv_hint(msg, context)
            return
        if text == BTN_PREV:
            await show_members(msg, context,
                               max(0, context.user_data.get("page", 0) - 1))
            return
        if text == BTN_NEXT:
            await show_members(msg, context,
                               context.user_data.get("page", 0) + 1)
            return
        if text == BTN_BACK:
            await show_main(msg, context, user_id)
            return
        uid = _pick_number(text, context)
        if uid is not None:
            context.user_data["return_to"] = "members"
            await show_card(msg, context, uid)
            return
        await msg.reply_text("Нажми номер участника или кнопку ниже.")
        return

    if screen in ("card", "card_after"):
        if text in (BTN_SLOW, BTN_SLOW_EDIT):
            await ask_slow(msg, context)
            return
        if text in (BTN_MUTE, BTN_MUTE_EDIT):
            await ask_mute(msg, context)
            return
        if text == BTN_UNSLOW:
            await remove_slow(msg, context)
            return
        if text == BTN_UNMUTE:
            await remove_mute(msg, context)
            return
        if text == BTN_DELETE:
            await ask_delete(msg, context)
            return
        if text == BTN_RESET:
            await reset_stats(msg, context)
            return
        if text == BTN_BACK:
            back = context.user_data.get("return_to", "members")
            if back == "restricted":
                await show_restricted(msg, context)
            else:
                await show_members(msg, context,
                                   context.user_data.get("page", 0))
            return
        await msg.reply_text("Выбери действие кнопками ниже.")
        return

    if screen == "slow_menu":
        if text == BTN_CUSTOM:
            await ask_slow_custom(msg, context)
            return
        if text == BTN_BACK:
            await show_card(msg, context,
                            context.user_data.get("selected"))
            return
        await msg.reply_text("Выбери интервал кнопками ниже.")
        return

    if screen == "mute_menu":
        if text == BTN_CUSTOM_SHORT:
            await ask_mute_custom(msg, context)
            return
        if text == BTN_BACK:
            await show_card(msg, context,
                            context.user_data.get("selected"))
            return
        await msg.reply_text("Выбери длительность кнопками ниже.")
        return

    if screen == "await_slow":
        if text == BTN_BACK:
            await ask_slow(msg, context)
            return
        await save_slow_custom(msg, context, text)
        return

    if screen == "await_mute":
        if text == BTN_BACK:
            await ask_mute(msg, context)
            return
        await save_mute_custom(msg, context, text)
        return

    if screen == "del_confirm":
        if text == BTN_DELETE_YES:
            await apply_delete(msg, context)
            return
        if text == BTN_BACK:
            await show_card(msg, context,
                            context.user_data.get("selected"))
            return
        return

    if screen == "await_add_id":
        if text == BTN_BACK:
            await show_members(msg, context, 0)
            return
        await save_add_id(msg, context, text)
        return

    if screen == "await_add_name":
        if text == BTN_BACK:
            context.user_data.pop("add_id", None)
            await show_members(msg, context, 0)
            return
        await save_add_name(msg, context, text)
        return

    if screen == "restricted":
        if text == BTN_BACK:
            await show_main(msg, context, user_id)
            return
        uid = _pick_number(text, context)
        if uid is not None:
            context.user_data["return_to"] = "restricted"
            await show_card(msg, context, uid)
            return
        await msg.reply_text("Нажми номер или кнопку ниже.")
        return

    if screen == "admins":
        if not me_super:
            await show_main(msg, context, user_id)
            return
        if text == BTN_ADMIN_ADD:
            await show_admin_pick(msg, context, 0)
            return
        if text == BTN_BACK:
            await show_main(msg, context, user_id)
            return
        uid = _pick_number(text, context)
        if uid is not None:
            await show_admin_card(msg, context, uid)
            return
        await msg.reply_text("Нажми номер админа или кнопку ниже.")
        return

    if screen == "admin_pick":
        if text == BTN_BACK:
            await show_admins(msg, context)
            return
        if text == BTN_PREV:
            await show_admin_pick(msg, context,
                                  max(0, context.user_data.get("page", 0) - 1))
            return
        if text == BTN_NEXT:
            await show_admin_pick(msg, context,
                                  context.user_data.get("page", 0) + 1)
            return
        uid = _pick_number(text, context)
        if uid is not None:
            await admin_pick_select(msg, context, uid)
            return
        await msg.reply_text("Выбери участника номером.")
        return

    if screen == "admin_card":
        if text == BTN_DELETE:
            await admin_ask_delete(msg, context)
            return
        if text == BTN_BACK:
            await show_admins(msg, context)
            return
        return

    if screen == "admin_del_confirm":
        if text == BTN_DELETE_YES:
            await admin_apply_delete(msg, context)
            return
        if text == BTN_BACK:
            await show_admin_card(msg, context,
                                  context.user_data.get("selected"))
            return
        return

    # неизвестный экран — сброс в главное
    await show_main(msg, context, user_id)


def build_app() -> Application:
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start,
                                   filters=filters.ChatType.PRIVATE))
    # CSV-файл в личке от админа
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Document.ALL, handle_csv))
    # вся панель — текст нижней клавиатуры
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        on_text))

    # Группа: все сообщения и медиа — тихая модерация
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.StatusUpdate.ALL, moderate_group))

    return app


async def _post_init(app: Application) -> None:
    await database.init_db()
    log.info("DB ready")


def main() -> None:
    if not config.BOT_TOKEN or config.BOT_TOKEN.startswith("ТОКЕН"):
        raise SystemExit("Заполни BOT_TOKEN в config.py или env BOT_TOKEN")
    app = build_app()
    app.post_init = _post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
