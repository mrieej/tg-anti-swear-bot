import os
import logging
import datetime
from aiohttp import web
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

# ID админа (можешь указать свой Telegram ID)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Список запрещённых слов
BAD_WORDS = [
    "дурак", "дура", "тупой", "тупая", "идиот", "идиотка",
    "писька", "жопа", "пошла в жопу", "пошел в жопу",
    "сука", "мразь"
]

# Счётчик предупреждений
WARNINGS = {}


# Команды
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 👋 Я бот-модератор.\n"
        "Я выдаю предупреждения за оскорбления.\n"
        "Если их будет 3 — замучу на 30 секунд ⏳.\n"
        "Попробуй /ping 🚀"
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Я живой и работаю!")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Бот активен и фильтрует сообщения.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Список команд:\n/start\n/ping\n/status\n/help")


# Проверка текста
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    chat = update.message.chat
    text = update.message.text.lower()

    # Проверка на плохие слова
    for bad_word in BAD_WORDS:
        if bad_word in text:
            user_id = user.id
            WARNINGS[user_id] = WARNINGS.get(user_id, 0) + 1
            count = WARNINGS[user_id]

            # Сообщение админу
            if ADMIN_ID != 0:
                try:
                    await context.bot.send_message(
                        ADMIN_ID,
                        f"👮 Нарушение в чате <b>{chat.title}</b>\n"
                        f"👤 Пользователь: {user.mention_html()}\n"
                        f"💬 Сообщение: <code>{update.message.text}</code>\n"
                        f"⚠️ Предупреждений: {count}/3",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение админу: {e}")

            if count < 3:
                await update.message.reply_text(
                    f"⚠️ {user.first_name}, предупреждение {count}/3 за слово «{bad_word}»!"
                )
            else:
                WARNINGS[user_id] = 0  # сброс после мута
                try:
                    until_date = datetime.datetime.now() + datetime.timedelta(seconds=30)
                    await chat.restrict_member(
                        user_id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=until_date,
                    )
                    await update.message.reply_text(
                        f"⛔ {user.first_name} замучен на 30 секунд за повторные оскорбления!"
                    )
                except Exception as e:
                    logging.error(f"Ошибка при муте: {e}")
            return

    # Реакция на слово "бот"
    if "бот" in text:
        await update.message.reply_text("Я тут! 👀")


# Создание приложения
def main():
    if not BOT_TOKEN or not WEBHOOK_URL:
        raise RuntimeError("Нет BOT_TOKEN или WEBHOOK_URL в переменных окружения!")

    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("help", cmd_help))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # aiohttp веб-сервер
    web_app = web.Application()
    web_app.router.add_post("/webhook", app.webhook_handler)

    async def health(request):
        return web.Response(text="OK")

    web_app.router.add_get("/", health)

    # Запускаем сервер
    web.run_app(web_app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()