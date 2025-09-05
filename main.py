import logging
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
webhook_url = os.getenv("WEBHOOK_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Мурка здесь 🐶❤️")

# Твой хэндлер сообщений (ничего не убирал)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "мурка" in text and "как дела" in text:
        await update.message.reply_text("У Мурки все отлично! 🐾")
    elif "гулять" in text:
        await update.message.reply_text("Гулять? Ура! 🐕🎉")
    elif "мяч" in text:
        await update.message.reply_text("⚽ Лови мячик!")
    else:
        await update.message.reply_text("Мурка слушает тебя 👂🐶")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))

    # Сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Настраиваем вебхук правильно ✅
    async def setup(app):
        await app.bot.delete_webhook(drop_pending_updates=True)
        await app.bot.set_webhook(f"{webhook_url}/webhook")
    app.post_init = setup

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
    )

if __name__ == "__main__":
    main()