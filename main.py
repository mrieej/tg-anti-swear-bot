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
BAN_SECONDS = 30       # временный бан на 30 секунд

# Забавные фразы — стиль собачки Мурки 🐶
FUNNY_REPLIES = {
    "привет": [
        "Гав-гав! 🐾 Привет, друг!",
        "Вииии! Мурка рада тебя видеть 🐶",
        "О, привет! Пойдём гулять? 🌳",
    ],
    "гулять": [
        "Ура! 🐕 Я уже бегу за поводком!",
        "Гав! 🦴 Давай скорее на улицу!",
        "Мурка готова к прогулке, хвостиком машу! 🐾",
    ],
    "вкусняшк": [
        "Ого! 🍖 А можно мне тоже кусочек?",
        "Мурка обожает вкусняшки 😋",
        "Если это котлетка — я твоя навсегда 🐶❤️",
    ],
    "котлет": [
        "Вау, котлетка?! 😍 Я уже слюной залилась!",
        "Мурка любит котлетки больше всего 😋",
    ],
    "мяч": [
        "Гав-гав! 🎾 Кидай мячик, я поймаю!",
        "Я уже бегу за мячиком 🐾",
        "Мурка любит играть с мячиком, брошу тебе обратно 🐶",
    ],
    "кто ты": [
        "Я Мурка 🐕, собачка-модератор!",
        "Я твоя верная защитница от плохих слов 🐾",
        "Я Мурка! Люблю гулять, играть и ловить нарушителей 🐶",
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
    r"\bтуп(ой|ая|ые|орылый)\b",
    r"\bжоп\w*",
    r"\bписьк\w*",
    r"\bчушка\w*",
    r"\bчухан\w*",
    r"\bебан\w*",
    r"\bебанашк\w*",
    r"\bсм[оа]\b",
    r"\bмразь\w*",
    r"\bдебилк\w*",
    r"\bдебил\w*",
    r"\bдибилк\w*",
    r"\bдибил\w*",
    r"\bурод\w*",
    r"\bуродк\w*",
    r"\bуродин\w*",
    r"\bдаун\w*",
    r"\bдолбо[её]б\w*",
    r"\bкоз[её]л\w*",
    r"\bказел\w*",
    r"\bлох\w*",
    r"\bлошар\w*",
    r"\bчмон\w*",
    r"\bчмо\w*",
    r"\bговноед\w*",
    r"\bговноедк\w*",
    r"\bгнид\w*",
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

    # --- Забавные ответы (Мурка) 🐶 ---
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
            await msg.reply_html(f"⚠️ Гав! {name}, не ругайся, пожалуйста 🐶")
            st.last_warn_at = now
        return

    # Предупреждение
    if strikes < THRESHOLD:
        if now - st.last_warn_at > 15:
            warning_text = f"⚠️ Гав-гав! {name}, предупреждение ({strikes}/{THRESHOLD}) за плохие слова 🐾"
            await msg.reply_html(warning_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"👮 Чат {chat.title}: пользователь {name} получил предупреждение ({strikes}/{THRESHOLD}).",
                )
            st.last_warn_at = now
        return

    # Наказание (временный бан)
    try:
        me = await context.bot.get_chat_member(chat.id, context.bot.id)
        if me.can_restrict_members:
            until = datetime.now(timezone.utc) + timedelta(seconds=BAN_SECONDS)
            await context.bot.ban_chat_member(
                chat.id,
                user.id,
                until_date=until,
            )
            ban_text = f"⛔ Гав! {name} получает бан на {BAN_SECONDS} секунд! 🐶"
            await msg.reply_html(ban_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"🚫 Чат {chat.title}: {name} забанен на {BAN_SECONDS} секунд.",
                )
        else:
            funny_text = f"😅 {name}, тебе повезло — у Мурки нет прав! Но все знают, что ты нарушитель 🐾"
            await msg.reply_html(funny_text)
            if admin_chat_id:
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=f"⚠️ Чат {chat.title}: {name} избежал наказания (нет прав у бота).",
                )
        q.clear()
        st.last_warn_at = now
    except Exception as e:
        await msg.reply_html(f"⚠️ Ошибка при попытке наказать: {e}")


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Гав-гав! 🐶 Я Мурка, собачка-модератор!\n"
        "Я слежу за чатом и гавкаю на тех, кто ругается.\n"
        f"После {THRESHOLD} предупреждений — бан на {BAN_SECONDS} секунд.\n"
        "А ещё я люблю гулять, играть и вкусняшки 🐾"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки Мурки:\n"
        f"- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n"
        f"- Бан: {BAN_SECONDS} секунд\n"
        "🐶 Мурка всегда на страже!"
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