import logging
import os
import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# --- Анти-мат 🛑 ---
bad_words = ["дурак", "лох", "тупой", "сука", "блять", "хуй", "пидор", "ебать"]
warned_users = {}

# --- Реакции Мурки 🐶 ---
murka_commands = {
    "дай лапу": "🐾 Мурка дала тебе лапу!",
    "лапу": "🐾 Вот лапка!",
    "дай левую лапу": "🐾 Мурка протянула левую лапку!",
    "хочешь гулять": "🐕 Мурка уже у двери, готова гулять!",
    "гулять": "🐾 Пошли гулять!",
    "давай играть": "🎾 Мурка радостно прыгает и хочет играть!",
    "играть": "⚽ Принеси мяч, и будем играть!",
    "принеси мяч": "⚽ Вот твой мячик!",
    "дай мяч": "⚽ Держи мячик!",
    "как дела": "🐶 У Мурки всё отлично!",
    "кого ты любишь": "🐾 Конечно тебя ❤️",
    "хочешь вкусняшки": "🍖 Мурка всегда за вкусняшку!",
    "какая твоя любимая песня": "🎶 Aerosmith - What it takes! ууу🐺💃",
}

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user_id = msg.from_user.id
    text = msg.text.lower()

    # Проверка на мат
    if any(bad in text for bad in bad_words):
        if user_id not in warned_users:
            warned_users[user_id] = 1
            await msg.reply_text("⚠️ Мурка предупреждает: не ругайся!")
        else:
            await msg.reply_text("🚫 Ты заблокирован за мат!")
            try:
                await context.bot.ban_chat_member(msg.chat.id, user_id)
            except Exception as e:
                await msg.reply_text(f"Не удалось заблокировать: {e}")
        return

    # --- Команды Мурки 🐶 ---
    for key, reply in murka_commands.items():
        if key in text or text.startswith("мурка " + key):
            await msg.reply_text(reply)
            return

    # --- Конвертер валют 💱 ---
    if any(word in text for word in ["доллар", "евро", "руб", "курс", "usd", "eur", "rub"]):
        try:
            # Число (сумма)
            match = re.search(r"(\d+)", text)
            amount = float(match.group(1)) if match else 1.0

            # Словарь для распознавания
            currency_map = {
                "доллар": "USD",
                "usd": "USD",
                "евро": "EUR",
                "eur": "EUR",
                "руб": "RUB",
                "рубль": "RUB",
                "rub": "RUB",
            }

            # Определяем валюты
            found = [cur for word, cur in currency_map.items() if word in text]
            if len(found) >= 2:
                from_cur, to_cur = found[0], found[1]
            elif "курс" in text and len(found) == 1:
                # "курс доллар к рублю"
                from_cur, to_cur = found[0], "RUB" if found[0] != "RUB" else "USD"
            else:
                await msg.reply_text("Мурка не поняла, какие валюты конвертировать 🐶💱")
                return

            # Запрос к API
            url = f"https://api.exchangerate.host/convert?from={from_cur}&to={to_cur}&amount={amount}"
            r = requests.get(url, timeout=5)
            data = r.json()

            if "result" in data and data["result"]:
                await msg.reply_text(
                    f"{amount} {from_cur} = {round(data['result'], 2)} {to_cur} 💱"
                )
            else:
                await msg.reply_text("Не удалось получить курс 😢")
        except Exception as e:
            await msg.reply_text(f"Ошибка при конвертации: {e}")
        return

    # --- Ответ по умолчанию ---
    if "мурка" in text:
        await msg.reply_text("Мурка слушает тебя 👂🐶")


# --- Запуск ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()