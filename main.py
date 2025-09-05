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
BAN_SECONDS = 30       # наказание (бан) на 30 секунд

# Фразы для Мурки 🐶
MURKA_REPLIES = {
    "мурка как дела": [
        "Гав! У меня всё отлично 🐾",
        "Лучше всех! Ведь я собачка Мурка 🐶💖",
    ],
    "мурка кого ты любишь": [
        "Конечно же тебя, мой человек 🐾❤️",
        "Люблю всех, кто даёт вкусняшки 🍖",
    ],
    "мурка хочешь вкусняшки": [
        "Гав-гав! Давай скорее! 🦴",
        "Котлетку? Уууу, давай! 🍖",
    ],
    "мурка какая твоя любимая песня": [
        "Aerosmith - What It Takes! ууу🐺💃",
        "Я пою громко: ГАВ-ГАВ-ГАВ 🎶",
    ],
    "гулять": [
        "Пошли скорее гулять! 🐕🌳",
        "Ура! Гулять-гулять-гулять! 🐾",
    ],
    "вкусняшк": [
        "Дай котлетку! 🐶🍖",
        "Я обожаю вкусняшки, ммм 🦴",
    ],
    "котлет": [
        "Котлетка? Дай две! 🍖🐾",
        "Я за котлету всё сделаю 🐕",
    ],
    "дай мяч": [
        "⚽ Вот твой мячик, кидай обратно!",
        "⚽⚽⚽ Гав-гав, играем?",
    ],
    "принеси мяч": [
        "⚽ Я принесла! Давай ещё раз кинь!",
        "⚽ Нашла мячик, держи!",
    ],
    "мурка охраняй": [
        "Гррр! Я охраняю территорию 🛡️🐕",
        "Никто не пройдёт! 🐺",
    ],
    "мурка охраняешь": [
        "Конечно, я на посту! 🐾👮‍♀️",
        "Я всегда охраняю свой чат 🛡️",
    ],
    "мурка дай лапу": [
        "🐾 Вот тебе лапка!",
        "Лапку даю, только вкусняшку не забудь 🍖",
    ],
    "мурка дай правую лапу": [
        "🐾 Вот правая лапка!",
    ],
    "мурка дай левую лапу": [
        "🐾 Вот левая лапка!",
    ],
    "мурка скучно": [
        "Давай поиграем с мячиком ⚽",
        "Хочешь, покажу трюк? 🐶",
    ],
    "мурка заскучала": [
        "Гав! Давай что-нибудь сделаем вместе 🐾",
    ],
    "мурка спой песню": [
        "Гав-гав-гав-гав 🎶",
        "Аууууу 🐺🎵",
    ],
    "мурка попой": [
        "ГАВ-ГАВ-ГАВ! Это моя песня 🎤🐶",
    ],
    "мурка злая": [
        "Грррррр 😈🐕",
        "Лучше не шути со мной! 🐺",
    ],
    "мурка злой": [
        "Я могу быть страшной! 🐾👹",
        "Гав-гав! Не зли меня 🐕",
    ],
}

# Запрещённые слова и оскорбления
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
    r"\bтуп(ой|ая|ые|ые|орылый)\b",
    r"\bжоп\w*",
    r"\bписьк\w*",
    r"\bчушка\b",
    r"\bчухан\w*",
    r"\bебанашк\w*",
    r"\bсмо\b",
    r"\bмразь\b",
    r"\bдебил(ка)?\b",
    r"\bдибил(ка)?\b",
    r"\bурод(ка|ина)?\b",
    r"\bдаун\b",
    r"\bдолбоеб\w*",
    r"\bк[ао]зел\b",
    r"\bлох(и)?\b",
    r"\bлошар\w*",
    r"\bчмоня\b",
    r"\bчмо\b",
    r"\bговноед(ы|ка)?\b",
    r"\bгнида\b",
]
BAD_REGEXES = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]
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

    # --- Ответы Мурки 🐶 ---
    for key, answers in MURKA_REPLIES.items():
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
        if me.can_restrict_members:
            until = datetime.now(timezone.utc) + timedelta(seconds=BAN_SECONDS)
            await context.bot.ban_chat_member(
                chat.id,
                user.id,
                until_date=until,
            )
            ban_text = f"⛔ {name} получил бан на {BAN_SECONDS} секунд!"
            await msg.reply_html(ban_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🚫 В чате {chat.title} пользователь {name} получил БАН на {BAN_SECONDS} секунд.",
                )
        else:
            funny_text = f"⛔ {name}, тебе повезло, у меня нет прав, но все знают, что ты нарушитель 😂"
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
        "Гав-гав! 🐶 Я Мурка — твой модератор!\n"
        f"Я слежу за чатом и выдаю предупреждения за плохие слова.\n"
        f"После {THRESHOLD} предупреждений — бан на {BAN_SECONDS} секунд.\n"
        "А ещё я люблю гулять, вкусняшки и играть с мячиком ⚽"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки:\n"
        f"- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n"
        f"- Наказание: {BAN_SECONDS} секунд"
    )


# ---------- Запуск ----------
def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    port = int(os.getenv("PORT", 8443))
    webhook_url = os.getenv("WEBHOOK_URL")

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