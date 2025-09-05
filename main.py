import os
import re
import time
import random
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass

import requests
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
WINDOW_SECONDS = 60
THRESHOLD = 3
BAN_SECONDS = 30

# Фразы для Мурки 🐶
MURKA_REPLIES = {
    "бот": ["Кто звал? 🤖", "Я тут, я слежу 👀", "Не обижай меня, я стараюсь 😢", "Бот в деле, базар фильтруй 💪"],
    "барсик": ["Кажется это админ..."],
    "мура": ["Гав! 🐶 Тут Мурка!", "Мурка всегда рядом ❤️", "Мурка смотрит на тебя 👀"],
    "мурочка": ["Гав! 🐶 Тут Мурка!", "Мурка всегда рядом ❤️", "Мурка смотрит на тебя 👀"],
    "мурик": ["Гав! 🐶 Тут Мурка!", "Мурка всегда рядом ❤️", "Мурка смотрит на тебя 👀"],
    "мурка": ["Гав! 🐶 Тут Мурка!", "Мурка всегда рядом ❤️", "Мурка смотрит на тебя 👀"],
    "привет": ["Привет, человечек 👋", "Дарова! Как настроение?", "Опа, приветики-пистолетики 🔫", "Мурка машет лапкой 🐾"],
    "как дела": ["У меня всегда отлично, я же бот 😎", "Живу, работаю 24/7 🤖", "Лучше, чем у людей, не болею 😉", "Мурка радостно виляeт хвостиком 🐕"],
    "мурка кто ты": ["Я бот-модератор, твой ночной кошмар 😈", "Я твой друг, но только если без матов 😅", "Я искусственный разум. Почти Скайнет.", "Я Мурка, твоя охранница 🐶"],
    "гуля": ["Ура! 🐕 Кто сказал гулять?!", "Мурка уже бежит за поводком! 🐾", "Гулять — моё любимое занятие! 🌳","кто сказал гулять?"],
    "дай лапу": ["Вот лапка 🐾", "Мурка протянула лапу 🐶", "На, держи лапку ❤️"],
    "играть": ["Играть?! Мурка готова! 🎉", "Давай играть, я принесла мячик ⚽", "Игры — это моё всё 🐕","⚽️","🏀"],
    "мяч": ["⚽ Держи мячик!", "Мурка принесла тебе мяч 🐶", "Дай мячик, давай поиграем! 🎾","⚽️","🏀"],
    "вкусняшк": ["Мурка хочет вкусняшку 😋", "А можно котлетку? 🍖", "Угости Мурку чем-нибудь вкусным 🐾"],
    "любишь": ["Мурка любит всех хороших людей ❤️", "Конечно тебя! 🐶", "Мурка любит вкусняшки и гулять 🌳"],
    "песня": ["Aerosmith - What It Takes 🎶 ууу🐺💃", "Мурка напевает любимую песню 🎤"],
    "мурка как дела": ["Гав! У меня всё отлично 🐾", "Лучше всех! Ведь я собачка Мурка 🐶💖"],
    "мурка кого ты любишь": ["Конечно же тебя, мой человек 🐾❤️", "Люблю всех, кто даёт вкусняшки 🍖"],
    "мурка хочешь вкусняшки": ["Гав-гав! Давай скорее! 🦴", "Котлетку? Уууу, давай! 🍖"],
    "мурка какая твоя любимая песня": ["audio"],
    "котлет": ["Котлетка? Дай две! 🍖🐾", "Я за котлету всё сделаю 🐕"],
    "дай мяч": ["⚽ Вот твой мячик, кидай обратно!", "⚽⚽⚽ Гав-гав, играем?"],
    "принеси мяч": ["⚽ Я принесла! Давай ещё раз кинь!", "⚽ Нашла мячик, держи!"],
    "мурка охраняй": ["Гррр! Я охраняю территорию 🛡️🐕", "Никто не пройдёт! 🐺"],
    "охран": ["Гррр! Я охраняю территорию 🛡️🐕", "Никто не пройдёт! 🐺"],
    "мурка охраняешь": ["Конечно, я на посту! 🐾👮‍♀️", "Я всегда охраняю свой чат 🛡️"],
    "мурка дай лапу": ["🐾 Вот тебе лапка!", "Лапку даю, только вкусняшку не забудь 🍖"],
    "мурка дай правую лапу": ["🐾 Вот правая лапка!"],
    "мурка дай левую лапку": ["🐾 Вот левая лапка!"],
    "скучн": ["Давай поиграем с мячиком ⚽", "Хочешь, покажу трюк? 🐶"],
    "мурка заскучала": ["Гав! Давай что-нибудь сделаем вместе 🐾"],
    "мурка спой песню": ["audio"],
    "мурка пой": ["audio"],
    # добавим "мурка песня" как отдельный аудио-триггер
    "мурка песня": ["audio"],
    "мурка злая": ["Грррррр 😈🐕", "Лучше не шути со мной! 🐺"],
    "мурка злой": ["Я могу быть страшной! 🐾👹", "Гав-гав! Не зли меня 🐕"],
    "кинь кубик": ["🎲"],
    "кинь кость": ["🎲"],
    "давай болтать": ["Гав! Давай, но я еще учусь разговаривать как вы!"]
}

# Регексы для аудио – проверяем прежде всего
AUDIO_REGEXES = [
    re.compile(r"\bмурка\s+пой\b"),
    re.compile(r"\bмурка\s+спой( песню)?\b"),
    re.compile(r"\bмурка\s+песня\b"),
    re.compile(r"\bмурка[, ]+какая твоя любимая песня\b"),
]

BAD_PATTERNS = [
    r"\bх[уy][йиеяё]\w*", r"\bп[ие]зд[аыо]*\w*", r"\b[её]б\w*", r"\bбл[яе]д[ьй]*\w*", r"\bсук[аио]*\w*",
    r"\bмуд[ао]к\w*", r"\bпид[оa]р\w*", r"\bдура\w*", r"\bдурак\w*", r"\bтуп(ой|ая|ые|ые|орылый)\b",
    r"\bжоп\w*", r"\bписьк\w*", r"\bчушка\b", r"\bчухан\w*", r"\bебанашк\w*", r"\bсмо\b",
    r"\bмразь\b", r"\bдебил(ка)?\b", r"\bдибил(ка)?\b", r"\bурод(ка|ина)?\b", r"\bдаун\b",
    r"\bдолбоеб\w*", r"\bк[ао]зел\b", r"\bлох(и)?\b", r"\bлошар\w*", r"\bчмоня\b", r"\bчмо\b",
    r"\bговноед(ы|ка)?\b", r"\bгнида\b",
]
BAD_REGEXES = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]

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

    # 1) Сначала проверяем спец-фразы для аудио
    for rx in AUDIO_REGEXES:
        if rx.search(text):
            try:
                with open("song.mp3", "rb") as audio:
                    await msg.reply_audio(audio)
            except Exception:
                await msg.reply_text("Ой, песню потеряла 😿")
            return

    # 2) Затем остальные фразы — от длинных ключей к коротким
    for key in sorted(MURKA_REPLIES.keys(), key=len, reverse=True):
        answers = MURKA_REPLIES[key]
        if re.search(rf"\b{re.escape(key)}\b", text):
            if "audio" in answers:
                try:
                    with open("song.mp3", "rb") as audio:
                        await msg.reply_audio(audio)
                except Exception:
                    await msg.reply_text("Ой, песню потеряла 😿")
            else:
                await msg.reply_text(random.choice(answers))
            return

    # Проверка на плохие слова
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

    if chat.type == ChatType.PRIVATE:
        if now - st.last_warn_at > 15:
            await msg.reply_html(f"⚠️ {name}, аккуратнее с выражениями.")
            st.last_warn_at = now
        return

    if strikes < THRESHOLD:
        if now - st.last_warn_at > 15:
            warning_text = f"⚠️ {name}, предупреждение ({strikes}/{THRESHOLD}) за оскорбления."
            await msg.reply_html(warning_text)
            st.last_warn_at = now
        return

    try:
        me = await context.bot.get_chat_member(chat.id, context.bot.id)
        if me.can_restrict_members:
            until = datetime.now(timezone.utc) + timedelta(seconds=BAN_SECONDS)
            await context.bot.ban_chat_member(chat.id, user.id, until_date=until)
            await msg.reply_html(f"⛔ {name} получил бан на {BAN_SECONDS} секунд!")
        q.clear()
        st.last_warn_at = now
    except Exception as e:
        await msg.reply_html(f"⚠️ Ошибка: {e}")

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Гав-гав! 🐶 Я Мурка — твой модератор!\n"
        f"После {THRESHOLD} предупреждений — бан на {BAN_SECONDS} секунд.\n"
        "А ещё я люблю гулять, вкусняшки и играть с мячиком ⚽"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ Настройки:\n- Порог: {THRESHOLD} нарушений за {WINDOW_SECONDS} секунд\n- Наказание: {BAN_SECONDS} секунд"
    )

# ---------- Новая команда: напоминания ----------
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /remind <минуты> <текст>")
        return
    try:
        minutes = int(context.args[0])
        text = " ".join(context.args[1:])
    except ValueError:
        await update.message.reply_text("Укажи количество минут числом.")
        return

    await update.message.reply_text(f"⏰ Напоминание через {minutes} мин: {text}")
    await context.job_queue.run_once(
        lambda ctx: ctx.bot.send_message(update.effective_chat.id, f"🔔 Напоминание: {text}"),
        when=minutes * 60,
        chat_id=update.effective_chat.id,
        name=str(update.effective_chat.id),
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
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=f"{webhook_url}/webhook",
    )

if __name__ == "__main__":
    main()