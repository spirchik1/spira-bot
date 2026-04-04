import os
import time
import sqlite3
import threading
import telebot
from telebot import types
from flask import Flask

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHXbRqOJX1JavFC4-Bs_RqmcaH0V3kfSb8"
bot = telebot.TeleBot(BOT_TOKEN)
RENDER_URL = "https://spira-bot.onrender.com"

# ==========================================
# 2. РАБОТА С БАЗОЙ ДАННЫХ (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('spira_game.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER)''')
    conn.commit()
    return conn

db_conn = init_db()

def get_user(user_id, name):
    cursor = db_conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {"balance": row[0]}
    else:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, name, 1000))
        db_conn.commit()
        return {"balance": 1000}

def update_balance(user_id, amount):
    cursor = db_conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
    db_conn.commit()

# ==========================================
# 3. КНОПКИ МЕНЮ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол")
    markup.add("🎲 Кубик", "💰 Баланс", "🏆 Топ игроков")
    markup.add("ℹ️ Инструкция")
    return markup

# ==========================================
# 4. ЛОГИКА ИГР
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    get_user(message.from_user.id, message.from_user.first_name)
    welcome = (
        f"🤖 **S.P.I.R.A. 2.0: GAME EDITION**\n\n"
        f"Привет, {message.from_user.first_name}!\n"
        "Я игровой бот. Забудь про фото и политику — здесь только азарт.\n\n"
        "💰 На счету: 1000 SpiraCoins\n"
        "🛠 Создатель: spirchik\n\n"
        "Выбирай игру в меню!"
    )
    bot.send_message(message.chat.id, welcome, reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "💰 Баланс")
def balance(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    bot.reply_to(message, f"💳 Твой баланс: **{user['balance']} 🪙**", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "🏆 Топ игроков")
def top(message):
    cursor = db_conn.cursor()
    cursor.execute("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = cursor.fetchall()
    text = "🏆 **ТОП-10 ИГРОКОВ МИРА S.P.I.R.A.**\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0]} — {row[1]} 🪙\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in ["🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик"])
def play(message):
    user = get_user(message.from_user.id, message.from_user.first_name)
    bet = 100
    if user['balance'] < bet:
        bot.reply_to(message, "❌ Недостаточно монет! Подожди раздачи или попроси у админа.")
        return

    update_balance(message.from_user.id, -bet)
    
    emoji = {"🎰 Казино": "🎰", "🏀 Баскет": "🏀", "⚽ Футбол": "⚽", "🎲 Кубик": "🎲"}[message.text]
    dice_msg = bot.send_dice(message.chat.id, emoji=emoji)
    val = dice_msg.dice.value
    
    time.sleep(4) # Эффект ожидания

    win = 0
    if message.text == "🎰 Казино":
        # 1, 22, 43, 64 — это выигрышные комбинации в Телеграм для Казино
        if val in [1, 22, 43, 64]: win = 1000
        elif val in [16, 32, 48]: win = 400
    elif message.text in ["🏀 Баскет", "⚽ Футбол"]:
        if val >= 4: win = 300
    else: # Кубик
        if val >= 4: win = 250

    if win > 0:
        update_balance(message.from_user.id, win)
        bot.send_message(message.chat.id, f"🔥 ПРИЗ! +{win} 🪙")
    else:
        bot.send_message(message.chat.id, "👎 Продул. Попробуй еще раз!")

# ==========================================
# 5. СЕРВЕР
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. GAMES ACTIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
