# Telegram Anti-Swear Bot (Webhook version)

## 🚀 Возможности
- Предупреждает пользователей за мат
- Автоматически удаляет сообщения с матом
- Если за минуту 3 нарушения — мут на 30 секунд

## ⚙️ Локальный запуск
1. Скопируй `.env.example` в `.env` и впиши свой `BOT_TOKEN` и `WEBHOOK_URL`.
2. Установи зависимости:
   ```bash
   pip install -r requirements.txt
   ```
3. Запусти:
   ```bash
   python main.py
   ```

## ☁️ Деплой на Render
1. Заливаешь проект в GitHub.
2. Создаёшь Web Service на [Render](https://render.com).
3. В переменные окружения (`Environment`) указываешь:
   - `BOT_TOKEN=...`
   - `WEBHOOK_URL=https://имя-приложения.onrender.com`
4. Render автоматически запустит бота.
