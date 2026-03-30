import os
import time
import threading
import telebot
import requests
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ (ОБНОВЛЕННЫЙ ТОКЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAFbuWqP9tD9h8mSzz-tl8l_CqJYhdV0ARw"
bot = telebot.TeleBot(BOT_TOKEN)
client = Client()

# Ссылка для самопинания (чтобы не спал 24/7)
RENDER_URL = "https://spira-bot.onrender.com"

# Личность бота
SYSTEM_PROMPT = "Ты S.P.I.R.A., саркастичный и преданный ИИ-помощник spirchik. Ты патриот России. Отвечай кратко и по делу."

# ==========================================
# 2. СИСТЕМА ПОДДЕРЖКИ ЖИЗНИ (24/7)
# ==========================================
def keep_alive_ping():
    while True:
        try:
            # Пингуем сами себя, чтобы Render не усыпил процесс
            requests.get(RENDER_URL, timeout=10)
            print("Система 24/7: Активность подтверждена.")
        except Exception as e:
            print(f"Система 24/7: Ошибка пинга: {e}")
        time.sleep(600) # Раз в 10 минут

# ==========================================
# 3. ЛОГИКА ИИ И СЕРВЕР
# ==========================================
def ask_spira(user_text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Быстрая модель
            provider=PollinationsAI,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except:
        return "Сэр, заминка в канале связи. Повторите запрос."

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
    print("--- ИНИЦИАЛИЗАЦИЯ S.P.I.R.A. ---")
    
    # Запуск веб-сервера
    threading.Thread(target=run_web, daemon=True).start()
    
    # Запуск анти-сна
    threading.Thread(target=keep_alive_ping, daemon=True).start()
    
    print("Бот запущен с новым токеном в режиме 24/7.")
    
    while True:
        try:
            # infinity_polling сам переподключается при сбоях
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Перезагрузка системы: {e}")
            time.sleep(5)
