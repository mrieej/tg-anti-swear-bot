import os
import logging
from datetime import datetime, timedelta, timezone
from collections import deque
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

BAD_WORDS = [
    "дурак", "дура", "идиот", "тупой", "тупая",
    "писька", "жопа", "пошел в жопу", "пошла в жопу",
    "лох", "лошара", "сволочь", "тварь"
]

THRESHOLD = 2           # кол-во предупреждений до мута
MUTE_SECONDS = 30       # время мута

# Хранилище состояния пользователей
user_states = {}

class UserState:
    def __init__(self):
        self.strikes = 0
        self.queue = deque(maxlen=5)
        self.last_warn_at = datetime.min.replace(tzinfo=timezone.utc)

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await chat.send_message(
        "Привет! 👋 Я бот-модератор.\n"
        "Я удаляю оскорбления и могу замутить на 30 секунд.\n"
        "Используй /status чтобы узнать настройки.\n"
        "А ещё проверь меня через /ping 🚀"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await chat.send_message("✅ Я живой и работаю!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await chat.send_message(
        f"⚙️ Настройки:\n"
        f"- Плохие слова: {len(BAD_WORDS)}\n"
        f"- Предупреждений до мута: {THRESHOLD}\n"
        f"- Время мута: {MUTE_SECONDS} сек."
    )

# Фильтр сообщений
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not msg.text:
        return

    text = msg.text.lower()
    if not any(bad in text for bad in BAD_WORDS):
        return

    # Удаляем сообщение
    try:
        await msg.delete()
    except Exception as e:
        logger.warning(f"Не смог удалить сообщение: {e}")

    # Обновляем статистику
    state = user_states.setdefault(user.id, UserState())
    state.queue.append(datetime.now(timezone.utc))
    state.strikes += 1
    now = datetime.now(timezone.utc)

    name = user.mention_html()

    # Предупреждение
    if state.strikes < THRESHOLD:
        if now - state.last_warn_at > timedelta(seconds=15):
            await chat.send_message(
                f"⚠️ {name}, предупреждение за оскорбление "
                f"({state.strikes}/{THRESHOLD}).",
                parse_mode="HTML",
            )
            state.last_warn_at = now
        return

    # Мут
    try:
        until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_SECONDS)
        perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(
            chat.id,
            user.id,
            permissions=perms,
            until_date=until,
        )
        await chat.send_message(
            f"⛔ {name} замучен на {MUTE_SECONDS}с за оскорбления!",
            parse_mode="HTML",
        )
        state.queue.clear()
        state.last_warn_at = now
    except Exception as e:
        await chat.send_message(f"⚠️ Ошибка: {e}")

# Запуск
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))

    # Webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
    )

if __name__ == "__main__":
    main()