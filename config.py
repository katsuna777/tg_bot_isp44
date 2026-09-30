"""Конфиг бота. Заполни перед запуском."""
import os

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "ТОКЕН_ОТ_BOTFATHER")
SUPER_ADMIN_ID: int = int(os.getenv("SUPER_ADMIN_ID", "0"))
CHAT_ID: int = int(os.getenv("CHAT_ID", "0"))

DB_PATH: str = os.getenv("DB_PATH", "bot.db")

# Пагинация списков в панели
PAGE_SIZE: int = 10
