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
BOT_TOKEN = "8632196470:AAElov7Tc8HcMHrQxPesZgytkU6vBcg1LHg"
bot = telebot.TeleBot(BOT_TOKEN)
client = Client()

# Название твоего сервиса на Render (нужно для самопинания)
RENDER_URL = "https://spira-bot.onrender.com"

SYSTEM_PROMPT = "Ты S.P.I.R.A., саркастичный и преданный ИИ-помощник spirchik. Ты патриот России, вежлив к своим, тверд с врагами. Отвечай кратко и по существу."

# ==========================================
# 2. ФУНКЦИЯ "АНТИ-СОН" (24/7)
# ==========================================
def keep_alive_ping():
    while True:
        try:
            # Стучимся сами к себе, чтобы Render не усыпил сервис
            requests.get(RENDER_URL, timeout=10)
            print("Система 24/7: Пинг отправлен успешно.")
        except Exception as e:
            print(f"Система 24/7: Ошибка пинга: {e}")
        time.sleep(600) # Пинг каждые 10 минут

# ==========================================
# 3. ИИ И ВЕБ-СЕРВЕР
# ==========================================
def ask_spira(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            provider=PollinationsAI,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}]
        )
        return response.choices[0].message.content
    except:
        return "Сэр, помехи в эфире. Повторите запрос."

app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. OPERATIONAL 24/7", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 4. ОБРАБОТКА И ЗАПУСК
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, ask_spira(message.text))

if __name__ == "__main__":
    # Запуск веб-сервера
    threading.Thread(target=run_web, daemon=True).start()
    
    # Запуск системы самопинания (чтобы не спал 24/7)
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    print("S.P.I.R.A. переведен в автономный режим 24/7.")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=15)
        except Exception as e:
            print(f"Перезагрузка: {e}")
            time.sleep(5)
