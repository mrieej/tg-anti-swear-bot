import os
import re
import time
import random
import logging
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

# ------------ ЛОГИ ------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("anti_swear_bot")

# ------------ НАСТРОЙКИ ------------
WINDOW_SECONDS = 60     # окно подсчёта нарушений (сек)
THRESHOLD = 3           # сколько матов за окно до мута
MUTE_SECONDS = 30       # длительность мута (сек)
FUN_COOLDOWN = 6        # чтобы бот не флудил «фишками» (сек)

# Список матов (регулярки)
MAT_PATTERNS = [
    r"\bх[уy][йиеяё]\w*",
    r"\bп[ие]зд[аыо]*\w*",
    r"\b[её]б\w*",
    r"\bбл[яе]д[ьй]*\w*",
    r"\bсук[аио]*\w*",
    r"\bмуд[ао]к\w*",
    r"\bпид[оa]р\w*",
]
MAT_REGEXES = [re.compile(p, re.IGNORECASE) for p in MAT_PATTERNS]

# Триггеры «фишек»
RX = lambda p: re.compile(p, re.IGNORECASE)
TRIGGERS = {
    "bot": [
        RX(r"\bбот\b"),
    ],
    "hello": [
        RX(r"\bприв(ет|ки)?\b"),
        RX(r"\bздравствуй(те)?\b"),
        RX(r"\bсалют\b"),
        RX(r"\bку\b"),
    ],
    "thanks": [
        RX(r"\bспасиб(о|ки)\b"),
        RX(r"\bблагодар(?:ю|ствую)\b"),
        RX(r"\bмерси\b"),
    ],
    "laugh": [
        RX(r"\b(ах{1,}а+|хаха|лол|кек|xd)\b"),
    ],
    "morning": [
        RX(r"\bдоброе утро\b"),
    ],
    "night": [
        RX(r"\bспокойной ночи\b"),
        RX(r"\bдоброй ночи\b"),
        RX(r"\bспоки(нч)?\b"),
    ],
    "birthday": [
        RX(r"с дн(е|ё)м рожд"),
        RX(r"\bднюх"),
    ],
    "who": [
        RX(r"кто ты"),
        RX(r"что ты умеешь"),
    ],
}

REPLIES = {
    "bot": ["Да-да, я тут 🤖", "На связи! 🎧", "Слушаю, чем помочь?"],
    "hello": ["Привет! 👋", "Салют! ✌️", "Йоу! 🙌"],
    "thanks": ["Всегда пожалуйста 🙌", "Не за что 😉", "Обращайся!"],
    "laugh": ["ахах, ору 😂", "кек 😹", "та же реакция 😆"],
    "morning": ["Доброе утро! ☀️", "Бодрого утра! 🌅", "Пора покорять мир 🦾"],
    "night": ["Сладких снов 🌙", "Нежной ночи ✨", "Отдыхай, завтра будет лучше 😴"],
    "birthday": ["С днём рождения! 🎂🎉", "Поздравляю! Всех благ! 🥳"],
    "who": ["Я модератор: удаляю маты и могу замутить на 30с. Ещё умею немного болтать 😉"],
}

# ------------ СОСТОЯНИЕ ------------
violations = defaultdict(lambda: deque(maxlen=50))

@dataclass
class UserState:
    last_warn_at: float = 0.0
    last_fun_at: float = 0.0

state = defaultdict(UserState)
fun_enabled = defaultdict(lambda: True)  # можно выключать /fun_off

# ------------ ВСПОМОГАТЕЛЬНОЕ ------------
def find_trigger(text: str) -> str | None:
    """Возвращает ключ триггера, если что-то совпало."""
    for name, patterns in TRIGGERS.items():
        if any(p.search(text) for p in patterns):
            return name
    return None

async def maybe_fun_reply(update: Update, text: str, st: UserState):
    """Отправляет «фишечный» ответ (если включено и не флудим)."""
    chat = update.effective_chat
    msg = update.effective_message

    if not fun_enabled[chat.id]:
        return

    now = time.time()
    if now - st.last_fun_at < FUN_COOLDOWN:
        return

    trig = find_trigger(text)
    if not trig:
        return

    # Чуть случайности, чтобы не перебарщивал в группах
    must_reply = (chat.type == ChatType.PRIVATE) or (trig in {"bot", "birthday"})
    if not must_reply and random.random() < 0.35:  # ~35% шанс
        return

    st.last_fun_at = now
    await msg.reply_text(random.choice(REPLIES[trig]))

# ------------ ОСНОВНАЯ ЛОГИКА ------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not user or not msg.text:
        return

    text = msg.text.lower().strip()
    log.info("MSG chat=%s user=%s: %s", chat.id, user.id, text)

    # --- 1) Модерация матов ---
    if any(r.search(text) for r in MAT_REGEXES):
        key = (chat.id, user.id)
        now = time.time()
        q = violations[key]
        while q and now - q[0] > WINDOW_SECONDS:
            q.popleft()
        q.append(now)
        strikes = len(q)

        st = state[key]
        name = user.mention_html()

        # Удаляем сообщение
        try:
            await msg.delete()
        except Exception as e:
            log.warning("Не удалось удалить сообщение: %s", e)

        # Если это ЛС — просто мягко предупреждаем
        if chat.type == ChatType.PRIVATE:
            if now - st.last_warn_at > 15:
                await msg.reply_html(f"⚠️ {name}, аккуратнее с лексикой.")
                st.last_warn_at = now
            return

        # Предупреждение
        if strikes < THRESHOLD:
            if now - st.last_warn_at > 15:
                await msg.reply_html(
                    f"⚠️ {name}, предупреждение за мат ({strikes}/{THRESHOLD})."
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
            await msg.reply_html(f"⛔ {name} замучен на {MUTE_SECONDS}с за маты!")
            q.clear()
            st.last_warn_at = now
        except Exception as e:
            await msg.reply_html(f"⚠️ Ошибка при мутации: {e}")
        return

    # --- 2) «Фишки» (если матов нет) ---
    st = state[(chat.id, user.id)]
    await maybe_fun_reply(update, text, st)

# ------------ КОМАНДЫ ------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! 👋 Я бот-модератор.\n"
        f"Удаляю маты и могу замутить на {MUTE_SECONDS} секунд.\n"
        "Команды: /status /ping /fun_on /fun_off\n"
        "Попробуй написать «бот», «привет», «спасибо», «кек», «спокойной ночи» 😉"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        "⚙️ Настройки:\n"
        f"- Порог: {THRESHOLD} мата за {WINDOW_SECONDS} сек\n"
        f"- Мут: {MUTE_SECONDS} сек\n"
        f"- Фишки: {'включены' if fun_enabled[chat_id] else 'выключены'}"
    )

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Я живой и работаю!")

async def fun_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    fun_enabled[chat_id] = True
    await update.message.reply_text("🎉 Фишки включены!")

async def fun_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    fun_enabled[chat_id] = False
    await update.message.reply_text("🤫 Фишки выключены.")

# ------------ ЗАПУСК ------------
def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    port = int(os.getenv("PORT", 8443))
    webhook_url = os.getenv("WEBHOOK_URL")  # например: https://tg-anti-swear-bot.onrender.com (без слеша на конце)

    if not token or not webhook_url:
        raise RuntimeError("BOT_TOKEN и WEBHOOK_URL должны быть заданы через переменные окружения")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("fun_on", fun_on))
    app.add_handler(CommandHandler("fun_off", fun_off))
    app.add_handler(MessageHandler(filters.TEXT, handle_text))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
    )

if __name__ == "__main__":
    main()