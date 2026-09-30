"""Общие хелперы панели на ReplyKeyboard: форматирование, клавиатуры, проверки."""
from __future__ import annotations

from datetime import datetime, timezone

from telegram import KeyboardButton, ReplyKeyboardMarkup

import config
import database

MONTHS_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "мая", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}

# ---------- кнопки ----------
BTN_MEMBERS = "Участники"
BTN_RESTRICTED = "Ограниченные"
BTN_ADMINS = "Админы"
BTN_BACK = "Назад"
BTN_ADD = "Добавить"
BTN_CSV = "CSV"
BTN_SLOW = "Медленный режим"
BTN_SLOW_EDIT = "Изменить режим"
BTN_UNSLOW = "Снять ограничение"
BTN_MUTE = "Мут"
BTN_MUTE_EDIT = "Изменить мут"
BTN_UNMUTE = "Снять мут"
BTN_DELETE = "Удалить"
BTN_DELETE_YES = "Да, удалить"
BTN_CUSTOM = "Своё значение"
BTN_CUSTOM_SHORT = "Своё"
BTN_ADMIN_ADD = "Добавить админа"
BTN_RESET = "Сбросить счётчик"
BTN_PREV = "◀"
BTN_NEXT = "▶"

SLOW_PRESETS: dict[str, int] = {
    "Раз в 30 мин": 30,
    "Раз в час": 60,
    "Раз в 3 часа": 180,
    "Раз в день": 1440,
}
MUTE_PRESETS: dict[str, int] = {
    "1 час": 60,
    "3 часа": 180,
    "1 день": 1440,
}


def kb(*rows: list[str]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[_btn(b) for b in row] for row in rows],
        resize_keyboard=True,
        is_persistent=True,
    )


# ---------- цвета кнопок (Bot API: danger/success/primary) ----------
PRIMARY = "primary"  # синяя
SUCCESS = "success"  # зелёная
DANGER = "danger"    # красная

BUTTON_STYLES: dict[str, str] = {
    BTN_MEMBERS: PRIMARY,
    BTN_RESTRICTED: PRIMARY,
    BTN_ADMINS: PRIMARY,
    BTN_ADD: SUCCESS,
    BTN_CSV: SUCCESS,
    BTN_ADMIN_ADD: SUCCESS,
    BTN_SLOW: PRIMARY,
    BTN_SLOW_EDIT: PRIMARY,
    BTN_UNSLOW: SUCCESS,
    BTN_MUTE: DANGER,
    BTN_MUTE_EDIT: DANGER,
    BTN_UNMUTE: SUCCESS,
    BTN_DELETE: DANGER,
    BTN_DELETE_YES: DANGER,
}
BUTTON_STYLES.update({label: PRIMARY for label in SLOW_PRESETS})
BUTTON_STYLES.update({label: DANGER for label in MUTE_PRESETS})


def _btn(text: str) -> KeyboardButton:
    style = BUTTON_STYLES.get(text)
    if style:
        return KeyboardButton(text, api_kwargs={"style": style})
    return KeyboardButton(text)


def main_menu_kb(is_super: bool) -> ReplyKeyboardMarkup:
    rows = [[BTN_MEMBERS], [BTN_RESTRICTED]]
    if is_super:
        rows.append([BTN_ADMINS])
    return kb(*rows)


def fmt_until(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return f"{dt.strftime('%H:%M')} {dt.day} {MONTHS_RU[dt.month]}"


def fmt_created(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
    return f"{dt.day} {MONTHS_RU[dt.month]} {dt.strftime('%H:%M')}"


def interval_label(minutes: int) -> str:
    if minutes < 60:
        return f"раз в {minutes} мин"
    hours = minutes / 60
    if hours == 1:
        return "раз в час"
    if hours == 3:
        return "раз в 3 часа"
    if hours == 24:
        return "раз в день"
    if hours.is_integer():
        return f"раз в {int(hours)} ч"
    return f"раз в {minutes} мин"


async def is_super(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID


async def check_admin(update) -> bool:
    """True если отправитель — админ (для лички). Чужих молча игнорируем."""
    user = update.effective_user
    if user is None or not await database.is_admin(user.id):
        return False
    return True


def display_name(full_name: str | None, username: str | None,
                 user_id: int) -> str:
    base = full_name or f"ID {user_id}"
    if username:
        u = username if username.startswith("@") else f"@{username}"
        return f"{base} {u}"
    return base


async def send_screen(message, context, text: str,
                      markup: ReplyKeyboardMarkup):
    """Одно меню за раз: стираем прошлое сообщение панели, шлём новое."""
    old_id = context.user_data.get("menu_msg_id")
    if old_id:
        try:
            await message.chat.delete_message(old_id)
        except Exception:
            pass
    sent = await message.reply_html(text, reply_markup=markup)
    context.user_data["menu_msg_id"] = sent.message_id
    return sent
