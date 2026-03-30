import os
import time
import threading
import telebot
import requests
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ (НОВЕЙШИЙ ТОКЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAFw1I5MdQhdSjs2MfOigaK0HvJ2YaIgi0o"
bot = telebot.TeleBot(BOT_TOKEN)
client = Client()

# Ссылка для самопинания (чтобы Render не спал)
RENDER_URL = "https://spira-bot.onrender.com"

# Личность бота: Умный, саркастичный, патриот России
SYSTEM_PROMPT = "Ты S.P.I.R.A., преданный ИИ-помощник spirchik. Ты патриот России. Отвечай по существу вопроса, будь ироничным, но полезным."

# ==========================================
# 2. СИСТЕМА ПОДДЕРЖКИ ЖИЗНИ (24/7)
# ==========================================
def keep_alive_ping():
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("Система 24/7: Активность подтверждена.")
        except Exception as e:
            print(f"Система 24/7: Ошибка пинга: {e}")
        time.sleep(600) # Раз в 10 минут

# ==========================================
# 3. ЛОГИКА ИИ (ВОЗВРАТ К СТАБИЛЬНОЙ МОДЕЛИ)
# ==========================================
def ask_spira(user_text):
    try:
        response = client.chat.completions.create(
            model="openai", # Стабильная модель (медленнее, но надежнее)
            provider=PollinationsAI,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return "Сэр, заминка в канале связи. Попробуйте еще раз."

app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. STATUS: ACTIVE 24/7", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 4. ОБРАБОТКА И БЕСКОНЕЧНЫЙ ЗАПУСК
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, ask_spira(message.text))

if __name__ == "__main__":
    print("--- ВОССТАНОВЛЕНИЕ СИСТЕМ S.P.I.R.A. ---")
    
    # Запуск веб-сервера
    threading.Thread(target=run_web, daemon=True).start()
    
    # Запуск анти-сна
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    print("Бот запущен на стабильной модели в режиме 24/7.")
    
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Перезагрузка: {e}")
            time.sleep(5)
