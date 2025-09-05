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

# Забавные фразы
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
    r"\bтуп(ой|ая|ые|ые)\b",
    r"\bжоп\w*",
    r"\bписьк\w*",
]
BAD_REGEXES = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]

# Хранилище нарушений
violations = defaultdict(lambda: deque(maxlen=50))

@dataclass
class UserState:
    last_warn_at: float = 0.0
    shame_count: int = 0  # сколько раз не смогли наказать

state = defaultdict(UserState)

# Псевдонимы (алиасы) для «позорников»: ключ = (chat_id, user_id) -> str
aliases = {}

def mention_with_alias(user, chat_id):
    """Упомянуть пользователя с кастомной подписью, если она есть."""
    label = aliases.get((chat_id, user.id)) or (user.first_name or "user")
    # Кликабельное упоминание с кастомным текстом
    return f'<a href="tg://user?id={user.id}">{label}</a>'


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
    name = mention_with_alias(user, chat.id)  # <-- используем алиас, если есть

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
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_chat_id),
                        text=f"👮 В чате {chat.title} пользователь {user.full_name} получил предупреждение ({strikes}/{THRESHOLD}).",
                    )
                except Exception as e:
                    print(f"ADMIN_LOG_CHAT_ID send error: {e}")
            st.last_warn_at = now
        return

    # Наказание
    try:
        me = await context.bot.get_chat_member(chat.id, context.bot.id)
        can_restrict = getattr(me, "can_restrict_members", False)

        if can_restrict:
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
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_chat_id),
                        text=f"🚫 В чате {chat.title} пользователь {user.full_name} получил БАН на {MUTE_SECONDS} секунд.",
                    )
                except Exception as e:
                    print(f"ADMIN_LOG_CHAT_ID send error: {e}")
            q.clear()
            st.shame_count = 0  # сбросим «позор»
        else:
            # нет прав — позорим и считаем
            st.shame_count += 1
            shame_messages = [
                f"😂 {name}, у меня нет прав замутить тебя, но ты официально ПОЗОР чата 🤡",
                f"👀 {name}, снова позоришься! Все уже запомнили тебя как нарушителя 😅",
                f"🤣 {name}, уровень ПОЗОРА: БОСС! Все смеются над тобой 😂",
                f"🔥 {name}, твой позор становится легендой, чату без тебя скучно 😈",
            ]
            msg_text = shame_messages[min(st.shame_count - 1, len(shame_messages) - 1)]
            await msg.reply_html(msg_text)

            # На 5-й и далее — попытка дать титул админу (если нарушитель админ),
            # иначе вешаем внутренний «псевдоним» 🤡 Позорник {first_name}
            if st.shame_count >= 5:
                applied = False
                # 1) Попробуем выдать custom title, если у бота есть право и юзер админ
                try:
                    victim_cm = await context.bot.get_chat_member(chat.id, user.id)
                    is_admin = victim_cm.status in ("administrator", "creator")
                    can_set_title = getattr(me, "can_promote_members", False)
                    if is_admin and can_set_title:
                        new_title = "🤡 Позорник"
                        await context.bot.set_chat_administrator_custom_title(chat.id, user.id, new_title)
                        await msg.reply_html(f"🎭 {name} получил титул администратора: <b>{new_title}</b>")
                        applied = True
                except Exception as e:
                    # просто сообщим, но не падаем
                    await msg.reply_html(f"⚠️ Хотел выдать титул, но не вышло: {e}")

                # 2) Если титул не вышло — даём внутренний алиас
                if not applied:
                    aliases[(chat.id, user.id)] = f"🤡 Позорник {user.first_name or 'user'}"
                    await msg.reply_html(
                        f"🏷 Теперь я буду звать тебя: <b>{aliases[(chat.id, user.id)]}</b>."
                    )

            if admin_chat_id:
                try:
                    await context.bot.send_message(
                        chat_id=int(admin_chat_id),
                        text=(f"⚠️ В чате {chat.title} {user.full_name} снова нарушил, "
                              f"но у бота нет прав. ПОЗОРный счётчик: {st.shame_count}."),
                    )
                except Exception as e:
                    print(f"ADMIN_LOG_CHAT_ID send error: {e}")

        st.last_warn_at = now
    except Exception as e:
        await msg.reply_html(f"⚠️ Ошибка при наказании: {e}")


# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 👋 Я модератор-бот!\n"
        f"После {THRESHOLD} предупреждений — бан на {MUTE_SECONDS} секунд (если есть права).\n"
        "Если прав нет — включается ПОЗОР-режим 🤡 с псевдонимом."
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки:\n"
        f"- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n"
        f"- Наказание: {MUTE_SECONDS} секунд\n"
        f"- Позорный счётчик и алиасы включены 🤡"
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