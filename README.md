# College Moderation Bot

Тихий модератор приватной Telegram-группы + панель управления в личке
на нижних клавиатурах (ReplyKeyboard, цветные кнопки).

## Настройка

```bash
pip install -r requirements.txt
export BOT_TOKEN="токен_от_BotFather"
export SUPER_ADMIN_ID="твой_user_id"
export CHAT_ID="id_группы_вида_-100xxx"
python main.py
```

Без env можно вписать значения прямо в `config.py`.

## Деплой

Systemd-юнит: `college-bot.service` (`systemctl enable/start bot`).
