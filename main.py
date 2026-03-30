import os
import time
import threading
import telebot
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ (ТОКЕН ВСТАВЛЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAGvrAgQczmegYRJN1YOgoyT_tKiacazQ_A"
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 2. ИНИЦИАЛИЗАЦИЯ ИИ (S.P.I.R.A.)
# ==========================================
client = Client()

SYSTEM_PROMPT = """Ты S.P.I.R.A. (Systematic Positronic Intelligent Responsive Android). 
Твой создатель - spirchik. Ты саркастичный, умный и преданный ИИ-помощник. 
Отвечай четко, по делу, как передовая нейросеть."""

def ask_spira(user_text):
    try:
        response = client.chat.completions.create(
            model="openai",
            provider=PollinationsAI,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Сэр, возникла заминка в нейронных связях: {e}"

# ==========================================
# 3. ВЕБ-СЕРВЕР ДЛЯ ПОДДЕРЖКИ ЖИЗНИ (RENDER)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. System Status: ACTIVE", 200

def run_web():
    # Автоматический подбор порта под требования Render
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 4. ОБРАБОТКА КОМАНД И СООБЩЕНИЙ
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Системы S.P.I.R.A. инициализированы. Я в сети и готов к работе, сэр. 🦾")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    bot.send_chat_action(message.chat.id, 'typing')
    answer = ask_spira(message.text)
    bot.reply_to(message, answer)

# ==========================================
# 5. ЗАПУСК СИСТЕМЫ (БРОНЕБОЙНЫЙ ЦИКЛ)
# ==========================================
if __name__ == "__main__":
    print("--- ЗАПУСК S.P.I.R.A. ---")
    
    # Запускаем Flask в отдельном потоке, чтобы Render видел порт
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    print("Веб-интерфейс активен.")
    
    time.sleep(2) # Даем серверу прогрузиться
    
    print("Подключение к шлюзам Telegram...")
    
    # Бесконечный цикл перезапуска при сбоях сети
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            print(f"Ошибка соединения: {e}. Перезагрузка через 5 секунд...")
            time.sleep(5)
