import os
from flask import Flask
from threading import Thread
import telebot
import g4f
from g4f.client import Client
import phonenumbers
from phonenumbers import carrier, geocoder

# 1. Инициализация Flask
app = Flask('')

@app.route('/')
def home():
    return "S.P.I.R.A. в строю 24/7"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# 2. Настройки бота
TOKEN = "8632196470:AAGvrAgQczmegYRJN1YOgoyT_tKiacazQ_A"
bot = telebot.TeleBot(TOKEN)
client = Client()

SYSTEM_PROMPT = """Ты — S.P.I.R.A., интеллектуальный ИИ-ассистент...""" # Тут твой промпт

# ... (весь твой код с хендлерами и ask_spira остается без изменений) ...

# 3. ПРАВИЛЬНЫЙ ЗАПУСК
if __name__ == "__main__":
    # Сначала запускаем веб-сервер в отдельном потоке
    server_thread = Thread(target=run_web)
    server_thread.daemon = True
    server_thread.start()
    
    print("S.P.I.R.A. выходит на связь...")
    # Теперь запускаем самого бота в основном потоке
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"Ошибка поллинга: {e}")
