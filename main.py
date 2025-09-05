import os
import re
import time
import random
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

# Настройки
WINDOW_SECONDS = 60    # окно для подсчёта нарушений
THRESHOLD = 3          # сколько раз можно нарушить
MUTE_SECONDS = 30      # наказание (бан/мут) на 30 секунд

# Забавные фразы (оригинальные + "собачьи")
FUNNY_REPLIES = {
    "бот": [
        "Кто звал? 🤖",
        "Я тут, я слежу 👀",
        "Не обижай меня, я стараюсь 😢",
        "Бот в деле, базар фильтруй 💪",
    ],
    "привет": [
        "Привет, человечек 👋",
        "Дарова! Как настроение?",
        "Опа, приветики-пистолетики 🔫",
    ],
    "как дела": [
        "У меня всегда отлично, я же бот 😎",
        "Живу, работаю 24/7 🤖",
        "Лучше, чем у людей, не болею 😉",
    ],
    "кто ты": [
        "Я бот-модератор, твой ночной кошмар 😈",
        "Я твой друг, но только если без матов 😅",
        "Я искусственный разум. Почти Скайнет.",
    ],

    # --- Новые триггеры: маленькая собачка ---
    "гав": [
        "гав-гав! маленький модератор на страже! 🐶",
        "тяв! кто тут ругается? я все слышу 👂🐾",
        "носик занюхал токсичность… фыр-фыр! 🚫🐶",
        "если будешь хорошим — дам лапку! 🐾",
    ],
    "тяв": [
        "тяв-тяв! порядок в чате — моя косточка! 🦴",
        "мелкий, но строгий модератор на посту 🐶",
        "тут нельзя ругаться, понял? тяв! 😠🐾",
    ],
    "собачка": [
        "я маленькая охрана чата, гав! 🐶",
        "ляг рядом и не ругайся — будет вкусняшка 🍖",
        "лапы заняты делом, следим за порядком 🐾",
    ],
    "песик": [
        "пёсик тут! не кусаюсь, если без матов 🐶",
        "тяв-тяв, держим чат в чистоте! 🧼",
        "нюх на токсичность прокачан на 100% 👃✨",
    ],
    "пёсик": [
        "пёсик тут! не кусаюсь, если без матов 🐶",
        "тяв-тяв, держим чат в чистоте! 🧼",
        "нюх на токсичность прокачан на 100% 👃✨",
    ],
    "щенок": [
        "щеночек-модератор дежурит! 🐶",
        "не ругайся, а то лишу косточки! 🦴",
        "если что — дам лапу поддержки 🐾",
    ],
    "дай лапу": [
        "держи лапку! 🤝🐾 только без грубостей!",
        "лапка пожата — давай жить дружно 🐶",
    ],
    "косточка": [
        "косточка выдаётся за вежливость 🦴✨",
        "косточку получают только хорошие ребята! 🐶",
    ],
}

# Запрещённые слова и оскорбления (расширенный список)
BAD_PATTERNS = [
    r"\bх[уy][йиеяё]\w*",
    r"\bп[ие]зд[аыо]*\w*",
    r"\b[её]б\w*",
    r"\bбл[яе]д[ьй]*\w*",
    r"\bсук[аио]*\w*",
    r"\bмуд[ао]к\w*",
    r"\bпид[оa]р\w*",
    r"\bдура\w*",
    r"\bдурак\w*",
    r"\bтуп(ой|ая|ые|ые)\b",
    r"\bжоп\w*",
    r"\bписьк\w*",

    # --- Ранее добавленные ---
    r"\bурод\w*",
    r"\bидиот\w*",
    r"\bкретин\w*",
    r"\bимбецил\w*",
    r"\bнедоум\w*",
    r"\bд[оа]лб[ао][её]б\w*",
    r"\bеблан\w*",
    r"\bу[её]бищ\w*",
    r"\bнах(ер|рен|уй)\w*",
    r"\bгандон\w*",
    r"\bчм[оё]\w*",
    r"\bмраз[ьи]\w*",
    r"\bсволоч\w*",
    r"\bтвар[ьи]\w*",
    r"\bскотин\w*",
    r"\bублюд\w*",
    r"\bгнид\w*",
    r"\bговн\w*",
    r"\bдерьм\w*",
    r"\bшлюх\w*",
    r"\bпроститут\w*",
    r"\bкурв\w*",
    r"\bпетух\w*",
    r"\bссыкун\w*",
    r"\bобосран\w*",
    r"\bлох\w*",

    # --- Новые по твоему списку ---
    r"\bдебилк\w*",
    r"\bкоз[аеё]\w*",
    r"\bдебил\w*",
    r"\bтупорыл\w*",
    r"\bебанашк\w*",
    r"\bебаный\w*",
    r"\bурод\w*",
    r"\bскотина\w*",
    r"\bгнида\w*",
    r"\bмразь\w*",
    r"\bблять\w*",
    r"\bлох\w*",
    r"\bлохи\w*",
    r"\bдебик\w*",
    r"\bчмон[яи]\w*",
    r"\bсучк\w*",
    r"\bсука\w*",
    r"\bговноед\w*",
    r"\bговноедк\w*",
    r"\bчушк\w*",
    r"\bчухан\w*",
]
BAD_REGEXES = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]

# Хранилище нарушений
violations = defaultdict(lambda: deque(maxlen=50))

@dataclass
class UserState:
    last_warn_at: float = 0.0

state = defaultdict(UserState)


# ---------- Логика ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not user or not msg.text:
        return

    text = msg.text.lower()

    # --- Забавные ответы ---
    for key, answers in FUNNY_REPLIES.items():
        if key in text:
            await msg.reply_text(random.choice(answers))
            return

    # --- Проверка на плохие слова ---
    if not any(r.search(text) for r in BAD_REGEXES):
        return

    key = (chat.id, user.id)
    now = time.time()
    q = violations[key]

    # удаляем старые нарушения
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    q.append(now)
    strikes = len(q)

    st = state[key]
    name = user.mention_html()

    admin_chat_id = os.getenv("ADMIN_LOG_CHAT_ID")

    # ЛС (просто предупреждение)
    if chat.type == ChatType.PRIVATE:
        if now - st.last_warn_at > 15:
            await msg.reply_html(f"⚠️ {name}, аккуратнее с выражениями.")
            st.last_warn_at = now
        return

    # Предупреждение
    if strikes < THRESHOLD:
        if now - st.last_warn_at > 15:
            warning_text = f"⚠️ {name}, предупреждение ({strikes}/{THRESHOLD}) за оскорбления."
            await msg.reply_html(warning_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"👮 В чате {chat.title} пользователь {name} получил предупреждение ({strikes}/{THRESHOLD}).",
                )
            st.last_warn_at = now
        return

    # Наказание
    try:
        me = await context.bot.get_chat_member(chat.id, context.bot.id)

        if me.status in ("administrator", "creator") and getattr(me, "can_restrict_members", True):
            until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_SECONDS)
            perms = ChatPermissions(can_send_messages=False)
            await context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=perms,
                until_date=until,
            )
            mute_text = f"⛔ {name} получил бан на {MUTE_SECONDS} секунд!"
            await msg.reply_html(mute_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🚫 В чате {chat.title} пользователь {name} получил БАН на {MUTE_SECONDS} секунд.",
                )
        else:
            funny_text = f"⛔ {name}, мне не дали права на блокировку 😢"
            await msg.reply_html(funny_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"⚠️ В чате {chat.title} пользователь {name} избежал наказания из-за отсутствия прав у бота.",
                )
        q.clear()
        st.last_warn_at = now
    except Exception as e:
        await msg.reply_html(f"⚠️ Ошибка при попытке наказать: {e}")


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 👋 Я модератор-бот!\n"
        "Я слежу за чатом и выдаю предупреждения за оскорбления.\n"
        f"После {THRESHOLD} предупреждений — бан на {MUTE_SECONDS} секунд.\n"
        "А ещё у меня есть смешные ответы 😉"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки:\n"
        f"- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n"
        f"- Наказание: {MUTE_SECONDS} секунд"
    )


# ---------- Запуск ----------
def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    port = int(os.getenv("PORT", 8443))
    webhook_url = os.getenv("WEBHOOK_URL")  # пример: https://tg-anti-swear-bot.onrender.com

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
    )


if __name__ == "__main__":
    main()
