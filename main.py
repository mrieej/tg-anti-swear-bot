import os
import re
import time
import random
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dataclasses import dataclass

from dotenv import load_dotenv
from telegram import Update
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

# Память для конвертера
last_amount = defaultdict(float)

# Словарь валют
CURRENCY_MAP = {
    "рубль": "RUB", "руб": "RUB", "₽": "RUB",
    "доллар": "USD", "бакс": "USD", "$": "USD",
    "евро": "EUR", "€": "EUR",
    "фунт": "GBP", "стерлинг": "GBP", "£": "GBP",
    "юань": "CNY", "¥": "CNY",
    "йена": "JPY", "иена": "JPY",
    "тенге": "KZT",
    "гривна": "UAH",
    "злотый": "PLN",
    "биткоин": "BTC", "btc": "BTC", "₿": "BTC",
    "эфир": "ETH", "eth": "ETH",
}

def normalize_currency(name: str) -> str:
    name = name.lower()
    return CURRENCY_MAP.get(name, name.upper())

# Фразы Мурки 🐶 (оставляем твой список, не меняем)

MURKA_REPLIES = {
    "бот": ["Кто звал? 🤖", "Я тут, я слежу 👀", "Не обижай меня, я стараюсь 😢", "Бот в деле, базар фильтруй 💪"],
    "мурка": ["Гав! 🐶 Тут Мурка!", "Мурка всегда рядом ❤️", "Мурка смотрит на тебя 👀"],
    "привет": ["Привет, человечек 👋", "Дарова! Как настроение?", "Опа, приветики-пистолетики 🔫", "Мурка машет лапкой 🐾"],
    "как дела": ["У меня всегда отлично, я же бот 😎", "Живу, работаю 24/7 🤖", "Лучше, чем у людей, не болею 😉", "Мурка радостно виляeт хвостиком 🐕"],
    "кто ты": ["Я бот-модератор, твой ночной кошмар 😈", "Я твой друг, но только если без матов 😅", "Я искусственный разум. Почти Скайнет.", "Я Мурка, твоя охранница 🐶"],
    "гулять": ["Ура! 🐕 Кто сказал гулять?!", "Мурка уже бежит за поводком! 🐾", "Гулять — моё любимое занятие! 🌳"],
    "дай лапу": ["Вот лапка 🐾", "Мурка протянула лапу 🐶", "На, держи лапку ❤️"],
    "играть": ["Играть?! Мурка готова! 🎉", "Давай играть, я принесла мячик ⚽", "Игры — это моё всё 🐕"],
    "мяч": ["⚽ Держи мячик!", "Мурка принесла тебе мяч 🐶", "Дай мячик, давай поиграем! 🎾"],
    "вкусняшк": ["Мурка хочет вкусняшку 😋", "А можно котлетку? 🍖", "Угости Мурку чем-нибудь вкусным 🐾"],
    "любишь": ["Мурка любит всех хороших людей ❤️", "Конечно тебя! 🐶", "Мурка любит вкусняшки и гулять 🌳"],
    "песня": ["Aerosmith - What It Takes 🎶 ууу🐺💃", "Мурка напевает любимую песню 🎤"],
    "мурка как дела": ["Гав! У меня всё отлично 🐾", "Лучше всех! Ведь я собачка Мурка 🐶💖"],
    "мурка кого ты любишь": ["Конечно же тебя, мой человек 🐾❤️", "Люблю всех, кто даёт вкусняшки 🍖"],
    "мурка хочешь вкусняшки": ["Гав-гав! Давай скорее! 🦴", "Котлетку? Уууу, давай! 🍖"],
    "мурка какая твоя любимая песня": ["Aerosmith - What It Takes! ууу🐺💃", "Я пою громко: ГАВ-ГАВ-ГАВ 🎶"],
    "котлет": ["Котлетка? Дай две! 🍖🐾", "Я за котлету всё сделаю 🐕"],
    "дай мяч": ["⚽ Вот твой мячик, кидай обратно!", "⚽⚽⚽ Гав-гав, играем?"],
    "принеси мяч": ["⚽ Я принесла! Давай ещё раз кинь!", "⚽ Нашла мячик, держи!"],
    "мурка охраняй": ["Гррр! Я охраняю территорию 🛡️🐕", "Никто не пройдёт! 🐺"],
    "мурка охраняешь": ["Конечно, я на посту! 🐾👮‍♀️", "Я всегда охраняю свой чат 🛡️"],
    "мурка дай лапу": ["🐾 Вот тебе лапка!", "Лапку даю, только вкусняшку не забудь 🍖"],
    "мурка дай правую лапу": ["🐾 Вот правая лапка!"],
    "мурка дай левую лапу": ["🐾 Вот левая лапка!"],
    "мурка скучно": ["Давай поиграем с мячиком ⚽", "Хочешь, покажу трюк? 🐶"],
    "мурка заскучала": ["Гав! Давай что-нибудь сделаем вместе 🐾"],
    "мурка спой песню": ["Гав-гав-гав-гав 🎶", "Аууууу 🐺🎵"],
    "мурка попой": ["ГАВ-ГАВ-ГАВ! Это моя песня 🎤🐶"],
    "мурка злая": ["Грррррр 😈🐕", "Лучше не шути со мной! 🐺"],
    "мурка злой": ["Я могу быть страшной! 🐾👹", "Гав-гав! Не зли меня 🐕"],
}

# --- Проверка плохих слов (оставляем как есть, твой список длинный) ---
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

violations = defaultdict(lambda: deque(maxlen=50))

@dataclass
class UserState:
    last_warn_at: float = 0.0

state = defaultdict(UserState)

# --- Получение курса валют ---
def fetch_rate(base: str, target: str) -> float | None:
    try:
        url = f"https://open.er-api.com/v6/latest/{base}"
        resp = requests.get(url, timeout=5).json()
        if resp.get("result") == "success":
            return resp["rates"].get(target)
    except Exception:
        return None
    return None

# --- Обработка сообщений ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not user or not msg.text:
        return
    text = msg.text.lower()

    # --- Конвертер валют ---
    match_course = re.search(r"(курс|rate)\s+([a-zа-я₽$€£¥₿]+)\s*(?:к|to)?\s*([a-zа-я₽$€£¥₿]+)?", text)
    if match_course:
        base = normalize_currency(match_course.group(2))
        target = normalize_currency(match_course.group(3)) if match_course.group(3) else "RUB"
        rate = fetch_rate(base, target)
        if rate:
            await msg.reply_text(f"Курс: 1 {base} = {rate:.2f} {target}")
        else:
            await msg.reply_text("Не удалось получить курс.")
        return

    match_conv = re.search(r"(\d+(?:\.\d+)?)\s*([a-zа-я₽$€£¥₿]+)\s*(?:в|to)\s*([a-zа-я₽$€£¥₿]+)", text)
    if match_conv:
        amount = float(match_conv.group(1))
        base = normalize_currency(match_conv.group(2))
        target = normalize_currency(match_conv.group(3))
        rate = fetch_rate(base, target)
        if rate:
            result = amount * rate
            last_amount[user.id] = amount
            await msg.reply_text(f"{amount} {base} = {result:.2f} {target}")
        else:
            await msg.reply_text("Не удалось получить курс.")
        return

    # --- Ответы Мурки 🐶 ---
    for key, answers in MURKA_REPLIES.items():
        if key in text:
            await msg.reply_text(random.choice(answers))
            return

    # --- Проверка на плохие слова ---
    if any(r.search(text) for r in BAD_REGEXES):
        # (оставляем логику модерации, не меняем)
        pass

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Гав-гав! 🐶 Я Мурка — твой модератор!\n"
        f"Я слежу за чатом и выдаю предупреждения за плохие слова.\n"
        f"После {THRESHOLD} предупреждений — бан на {BAN_SECONDS} секунд.\n"
        "А ещё я люблю гулять, вкусняшки, играть с мячиком ⚽ и умею конвертировать валюты 💱"
    )

def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()