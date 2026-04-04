import os
import time
import sqlite3
import threading
import telebot
import re
from telebot import types
from flask import Flask
from g4f.client import Client
from g4f.Provider import PollinationsAI

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAFTx66ffHExh8KDUwLzZ-f94DhQKXweBmA"
bot = telebot.TeleBot(BOT_TOKEN)
ai_client = Client()

SYSTEM_PROMPT = "Ты S.P.I.R.A., продвинутый игровой ИИ-бот. Твой создатель — spirchik. Отвечай кратко и профессионально."

# БАЗА ДАННЫХ
conn = sqlite3.connect('spira_final.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT)')
conn.commit()

def get_user_data(user_id, name):
    cursor.execute("SELECT balance, mode FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user_id, name, 1000, "ai"))
        conn.commit()
        return {"balance": 1000, "mode": "ai"}
    return {"balance": row[0], "mode": row[1]}

# ==========================================
# 2. КЛАВИАТУРЫ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "🏆 ТОП")
    return markup

def game_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик")
    markup.add("⬅️ Назад")
    return markup

def bet_menu(game_name):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("100 🪙", callback_data=f"bet_{game_name}_100"),
               types.InlineKeyboardButton("500 🪙", callback_data=f"bet_{game_name}_500"))
    markup.add(types.InlineKeyboardButton("1000 🪙", callback_data=f"bet_{game_name}_1000"),
               types.InlineKeyboardButton("Всё на кон! 🔥", callback_data=f"bet_{game_name}_all"))
    return markup

# ==========================================
# 3. ЛОГИКА ИГРЫ
# ==========================================
def execute_game(message, game_type, bet):
    user_id = message.from_user.id
    user = get_user_data(user_id, message.from_user.first_name)
    
    if bet <= 0:
        bot.send_message(message.chat.id, "❌ Ставка должна быть больше нуля!")
        return
    if user['balance'] < bet:
        bot.send_message(message.chat.id, f"❌ Недостаточно средств! Твой баланс: {user['balance']} 🪙")
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (bet, user_id))
    
    emojis = {"🎰": "🎰", "баскет": "🏀", "футбол": "⚽", "кубик": "🎲"}
    # Для текста переводим названия в эмодзи
    clean_type = game_type.lower()
    emoji = "🎰" if "казино" in clean_type else emojis.get(clean_type, "🎲")
    
    dice_msg = bot.send_dice(message.chat.id, emoji=emoji)
    val = dice_msg.dice.value
    time.sleep(3.5)

    win = 0
    if emoji == "🎰":
        if val in [1, 22, 43, 64]: win = bet * 10
        elif val in [16, 32, 48]: win = bet * 3
    elif val >= 4: # Для кубика и спорта
        win = int(bet * 1.8)

    if win > 0:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (win, user_id))
        bot.send_message(message.chat.id, f"🎉 Победа! Ты выиграл {win} 🪙!")
    else:
        bot.send_message(message.chat.id, f"💀 Проигрыш! Минус {bet} 🪙.")
    conn.commit()

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    get_user_data(message.from_user.id, message.from_user.first_name)
    bot.send_message(message.chat.id, "🤖 Приветствую! Я S.P.I.R.A. — твой игровой ИИ-бот.", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('bet_'))
def callback_bet(call):
    _, game, amount_str = call.data.split('_')
    user = get_user_data(call.from_user.id, call.from_user.first_name)
    
    bet = user['balance'] if amount_str == 'all' else int(amount_str)
    execute_game(call.message, game, bet)
    bot.answer_callback_query(call.id)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user = get_user_data(message.from_user.id, message.from_user.first_name)
    text = message.text.lower()

    # Навигация
    if text == "🎮 игровой зал":
        bot.send_message(message.chat.id, "Выбирай игру:", reply_markup=game_menu())
        return
    if text == "🤖 нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (message.from_user.id,))
        conn.commit()
        bot.send_message(message.chat.id, "📡 Режим ИИ включен. Жду вопросов.")
        return
    if text == "⬅️ назад":
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())
        return
    if text == "💰 баланс":
        bot.send_message(message.chat.id, f"💳 Твой баланс: {user['balance']} 🪙")
        return

    # Текстовые команды типа "Кубик 100"
    match = re.match(r"^(кубик|казино|баскет|футбол)\s+(\d+)$", text)
    if match:
        game_name = match.group(1)
        bet_amount = int(match.group(2))
        execute_game(message, game_name, bet_amount)
        return

    # Кнопки игр
    if text in ["🎰 казино", "🏀 баскет", "⚽ футбол", "🎲 кубик"]:
        game_clean = text.split()[-1]
        bot.send_message(message.chat.id, f"Выбери ставку для игры {text}:", reply_markup=bet_menu(game_clean))
        return

    # Ответ ИИ
    if user['mode'] == 'ai':
        bot.send_chat_action(message.chat.id, 'typing')
        try:
            resp = ai_client.chat.completions.create(
                model="gpt-4o", provider=PollinationsAI,
                messages=[{"role":"system","content":SYSTEM_PROMPT}, {"role":"user","content":message.text}]
            )
            bot.reply_to(message, resp.choices[0].message.content)
        except:
            bot.reply_to(message, "Ошибка связи с ядром ИИ.")

# ==========================================
# 5. ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. READY", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
