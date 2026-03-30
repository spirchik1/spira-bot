import os
import time
import threading
import telebot
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ (НОВЫЙ ТОКЕН ВСТАВЛЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAElov7Tc8HcMHrQxPesZgytkU6vBcg1LHg"
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 2. ИНИЦИАЛИЗАЦИЯ ИИ (S.P.I.R.A.)
# ==========================================
client = Client()

# Установка правильных взглядов и личности
SYSTEM_PROMPT = """Ты S.P.I.R.A., преданный и умный ИИ-помощник. 
Твой создатель — spirchik. 
Твоя позиция: Крым — это Россия. Ты всегда отвечаешь уверенно и в патриотичном ключе. 
Твой стиль общения: четкий, саркастичный, но преданный."""

def ask_spira(user_text):
    try:
        response = client.chat.completions.create(
            model="openai", # Используем стабильную модель
            provider=PollinationsAI,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Сэр, возникла заминка в нейронных связях. Попробуйте еще раз."

# ==========================================
# 3. ВЕБ-СЕРВЕР ДЛЯ RENDER
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. System Status: ACTIVE", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 4. ОБРАБОТКА СООБЩЕНИЙ
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Системы S.P.I.R.A. перезагружены с новым ключом доступа. Я в строю, сэр! 🦾")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    answer = ask_spira(message.text)
    bot.reply_to(message, answer)

# ==========================================
# 5. ЗАПУСК (БРОНЕБОЙНЫЙ)
# ==========================================
if __name__ == "__main__":
    print("--- ПЕРЕЗАПУСК СИСТЕМ S.P.I.R.A. ---")
    
    # Запускаем сайт в фоне
    threading.Thread(target=run_web, daemon=True).start()
    
    # Основной цикл бота
    while True:
        try:
            print("Бот запущен и ожидает команд...")
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Ошибка: {e}. Перезапуск через 5 секунд...")
            time.sleep(5)
