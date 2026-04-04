import os
import time
import random
import threading
import telebot
from telebot import types
from flask import Flask

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHn0VQpSRWFlzIDWJq-kRY1pt4-LN6JlZY"
bot = telebot.TeleBot(BOT_TOKEN)
RENDER_URL = "https://spira-bot.onrender.com"

# База данных в памяти (после перезагрузки обнулится, для вечного хранения нужна БД)
user_data = {} 

def get_user(user_id, name):
    if user_id not in user_data:
        user_data[user_id] = {"balance": 1000, "name": name}
    return user_data[user_id]

# ==========================================
# 2. МЕНЮ И КНОПКИ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскетбол", "⚽ Футбол")
    markup.add("🎲 Кубик", "💰 Баланс", "🏆 Топ игроков")
    markup.add("ℹ️ Инструкция")
    return markup

# ==========================================
# 3. ЛОГИКА ИГР
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    welcome_text = (
        f"🤖 **Система S.P.I.R.A. приветствует тебя, {message.from_user.first_name}!**\n\n"
        "Я — твой игровой и технологичный помощник.\n"
        "Здесь ты можешь зарабатывать SpiraCoins и соревноваться с другими.\n\n"
        "📍 **Твой баланс:** 1000 🪙\n"
        "📍 **Создатель:** spirchik\n\n"
        "Выбирай игру в меню ниже!"
    )
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💰 Баланс")
def check_balance(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    bot.reply_to(message, f"💳 Твой текущий счет: **{user['balance']} SpiraCoins**", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🏆 Топ игроков")
def leaderboard(message):
    top = sorted(user_data.items(), key=lambda x: x[1]['balance'], reverse=True)[:10]
    text = "🏆 **ГЛОБАЛЬНАЯ ТАБЛИЦА ЛИДЕРОВ** 🏆\n\n"
    for i, (uid, data) in enumerate(top, 1):
        text += f"{i}. {data['name']} — {data['balance']} 🪙\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# Универсальный обработчик игр со стикерами
@bot.message_handler(func=lambda message: message.text in ["🎰 Казино", "🏀 Баскетбол", "⚽ Футбол", "🎲 Кубик"])
def play_game(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    if user['balance'] < 100:
        bot.reply_to(message, "⚠️ Недостаточно SpiraCoins! Минимум для игры — 100.")
        return

    user['balance'] -= 100
    emoji = {"🎰 Казино": "🎰", "🏀 Баскетбол": " basketball", "⚽ Футбол": "⚽", "🎲 Кубик": "🎲"}[message.text]
    
    # Отправляем игровой стикер
    msg = bot.send_dice(message.chat.id, emoji=emoji if message.text != "🏀 Баскетбол" else "🏀")
    value = msg.dice.value

    time.sleep(4) # Ждем анимацию

    win = 0
    if message.text == "🎰 Казино":
        if value in [1, 22, 43, 64]: # Джекпот (три семерки или одинаковые)
            win = 1000
        elif value in [16, 32, 48]: win = 300
    elif message.text in ["🏀 Баскетбол", "⚽ Футбол"]:
        if value >= 4: win = 250 # Попадание
    elif message.text == "🎲 Кубик":
        if value >= 4: win = 200

    if win > 0:
        user['balance'] += win
        bot.send_message(message.chat.id, f"🎉 **ПОБЕДА!** Ты выиграл {win} 🪙\nБаланс: {user['balance']}")
    else:
        bot.send_message(message.chat.id, f"❌ Проигрыш. Повезет в следующий раз!\nБаланс: {user['balance']}")

@bot.message_handler(func=lambda message: message.text == "ℹ️ Инструкция")
def info(message):
    text = (
        "📖 **ИНСТРУКЦИЯ S.P.I.R.A.**\n\n"
        "1. Каждая ставка стоит 100 🪙.\n"
        "2. В **Казино** самый большой куш.\n"
        "3. В **Спорте** шансы 50/50.\n"
        "4. Весь прогресс сохраняется в системе.\n\n"
        "Удачи, игрок!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ==========================================
# 4. СЕРВЕР И ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. GAMES ONLINE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
