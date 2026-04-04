import os
import time
import threading
import telebot
import requests
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAFw1I5MdQhdSjs2MfOigaK0HvJ2YaIgi0o"
bot = telebot.TeleBot(BOT_TOKEN)
client = Client()
RENDER_URL = "https://spira-bot.onrender.com"

# ОБНОВЛЕННЫЙ SYSTEM PROMPT (СТРОГИЕ ИНСТРУКЦИИ)
SYSTEM_PROMPT = (
    "Ты S.P.I.R.A., уникальный высокотехнологичный ИИ. "
    "На вопрос о создателе отвечай просто: 'Мой создатель — spirchik'. "
    "НИКОГДА не упоминай GPT, OpenAI и другие сторонние технологии. Ты — независимая разработка. "
    "Не упоминай создателя сам, если об этом не спросили. Никакой политики и патриотизма. "
    "Тон: спокойный, технологичный, преданный."
)

# ==========================================
# 2. ФУНКЦИЯ ИИ
# ==========================================
def ask_spira(user_text, image_url=None):
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if image_url:
            content = [
                {"type": "text", "text": user_text if user_text else "Проанализируй медиафайл."},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user_text})

        response = client.chat.completions.create(
            model="gpt-4o", 
            provider=PollinationsAI,
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "Сэр, канал связи перегружен. Повторите запрос позже."

# ==========================================
# 3. ОБРАБОТЧИКИ ТЕЛЕГРАМ
# ==========================================

@bot.message_handler(content_types=['text'])
def text_handler(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, ask_spira(message.text))

@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    bot.send_chat_action(message.chat.id, 'typing')
    file_info = bot.get_file(message.photo[-1].file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    bot.reply_to(message, ask_spira(message.caption, file_url))

@bot.message_handler(content_types=['voice', 'video_note'])
def voice_handler(message):
    # Заглушка для аудио, пока обрабатываем только факт получения
    bot.reply_to(message, "Принял медиафайл. Анализирую содержимое через внешние сенсоры...")

# ==========================================
# 4. СЕРВЕР И ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. 2.0 ACTIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    print("--- S.P.I.R.A. ОБНОВЛЕН И ГОТОВ К РАБОТЕ ---")
    bot.infinity_polling()
