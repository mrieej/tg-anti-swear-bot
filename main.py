import os
import re
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass

from dotenv import load_dotenv
from telegram import Update, ChatPermissions
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

# Настройки бота
WINDOW_SECONDS = 60   # окно подсчёта нарушений (в секундах)
THRESHOLD = 3         # сколько нарушений допустимо за окно
MUTE_SECONDS = 30     # длительность мута (в секундах)

# Список запрещённых слов и оскорблений
BAD_PATTERNS = [
    # маты
    r"\bх[уy][йиеяё]\w*",
    r"\bп[ие]зд[аыо]*\w*",
    r"\b[её]б\w*",
    r"\bбл[яе]д[ьй]*\w*",
    r"\bсук[аио]*\w*",
    r"\bмуд[ао]к\w*",
    r"\bпид[оa]р\w*",

    # оскорбления и запрещённые слова
    r"\bдурак\w*",
    r"\bтуп[ао]й\w*",
    r"\bидиот\w*",
    r"\bжоп\w*",
    r"\bписьк\w*",
    r"\bговн\w*",
    r"\bпош(ел|ёл)\s+в\s+жоп\w*",
]

BAD_REGEXES = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]

# Хранилище нарушений
violations = defaultdict(lambda: deque(maxlen=50))

@dataclass
class UserState:
    last_warn_at: float = 0.0

state = defaultdict(UserState)


# ---------- Логика обработки сообщений ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not user or not msg.text:
        return

    text = msg.text.lower()
    if not any(r.search(text) for r in BAD_REGEXES):
        return

    key = (chat.id, user.id)
    now = time.time()
    q = violations[key]
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    q.append(now)
    strikes = len(q)

    st = state[key]
    name = user.mention_html()

    # Автоудаление сообщения
    try:
        await msg.delete()
    except Exception:
        pass

    # ЛС
    if chat.type == ChatType.PRIVATE:
        if now - st.last_warn_at > 15:
            await msg.reply_html(f"⚠️ {name}, аккуратнее с выражениями.")
            st.last_warn_at = now
        return

    # Предупреждение
    if strikes < THRESHOLD:
        if now - st.last_warn_at > 15:
            await msg.reply_html(
                f"⚠️ {name}, предупреждение за оскорбление ({strikes}/{THRESHOLD})."
            )
            st.last_warn_at = now
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
        await msg.reply_html(f"⛔ {name} замучен на {MUTE_SECONDS}с за оскорбления!")
        q.clear()
        st.last_warn_at = now
    except Exception as e:
        await msg.reply_html(f"⚠️ Ошибка: {e}")


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋 Я бот-модератор.\n"
        f"Я удаляю маты и оскорбления. Если их слишком много — дам мут на {MUTE_SECONDS} секунд.\n"
        "Используй /status чтобы узнать настройки.\n"
        "Проверь меня через /ping 🚀"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки:\n"
        f"- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n"
        f"- Мут: {MUTE_SECONDS} секунд"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Я живой и работаю!")


# ---------- Запуск ----------
def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    port = int(os.getenv("PORT", 8443))
    webhook_url = os.getenv("WEBHOOK_URL")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
    )


if __name__ == "__main__":
    main()