import os, time, threading, sqlite3, re, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ (ОБНОВЛЕННЫЙ ТОКЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAGFnm-TikkUzMcNknpzuY7QXwT2C3-Fw3g"
BOT_USERNAME = "spiraaiofficial_bot" 
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=15)

SYSTEM_PROMPT = "Ты S.P.I.R.A., игровой ИИ. Твой создатель — spirchik. Отвечай кратко."

# БАЗА ДАННЫХ
def get_db_connection():
    return sqlite3.connect('spira_v7.db', check_same_thread=False)

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT)''')
conn.commit()

def get_u(m):
    uid = m.from_user.id
    cursor.execute("SELECT balance, mode, prefix FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", 
                       (uid, m.from_user.first_name, 1000, "off", "Новичок 🛡"))
        conn.commit()
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡"}
    return {"bal": row[0], "mode": row[1], "prefix": row[2]}

# ==========================================
# 2. ИНТЕРФЕЙС (КНОПКИ НА РУССКОМ)
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "👤 Кто я")
    markup.add("🛒 Магазин", "➕ Добавить в чат")
    return markup

def game_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик")
    markup.add("⬅️ Назад")
    return markup

# ==========================================
# 3. ЛОГИКА НЕЙРОСЕТИ
# ==========================================
def ask_ai(message):
    try:
        response = g4f.ChatCompletion.create(
            model=g4f.models.default,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message.text}],
        )
        if response:
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "📡 Сигнал ядра потерян.")
    except:
        bot.reply_to(message, "⚠️ Система ИИ на перезагрузке. Игры доступны.")

# ==========================================
# 4. КОМАНДЫ (АНГЛИЙСКИЙ)
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def help_cmd(m):
    get_u(m)
    text = (
        "🤖 **S.P.I.R.A. Системный терминал**\n\n"
        "**Команды:**\n"
        "/ai — Включить нейросеть\n"
        "/stop — Выключить нейросеть\n"
        "/profile — Профиль\n"
        "/balance — Счет\n"
        "/shop — Магазин\n\n"
        "**Игры:**\n"
        "/casino [ставка]\n"
        "/basket [ставка]\n"
        "/football [ставка]\n"
        "/dice [ставка]"
    )
    bot.send_message(m.chat.id, text, reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=['ai'])
def ai_on(m):
    cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
    conn.commit()
    bot.reply_to(m, "📡 Режим ИИ активирован.")

@bot.message_handler(commands=['stop'])
def ai_off(m):
    cursor.execute("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
    conn.commit()
    bot.reply_to(m, "🔌 Режим ИИ отключен.")

@bot.message_handler(commands=['profile'])
def profile_cmd(m):
    u = get_u(m)
    bot.reply_to(m, f"👤 **ПРОФИЛЬ:**\n🆔 ID: `{m.from_user.id}`\n🏷 Статус: {u['prefix']}\n💰 Баланс: {u['bal']} 🪙", parse_mode="Markdown")

@bot.message_handler(commands=['casino', 'basket', 'football', 'dice'])
def games(m):
    u = get_u(m)
    cmd = m.text.split()
    if len(cmd) < 2:
        return bot.reply_to(m, "⚠️ Укажи ставку. Пример: `/casino 100`", parse_mode="Markdown")
    
    try:
        amount = int(cmd[1])
        if u['bal'] < amount: return bot.reply_to(m, "❌ Недостаточно средств.")
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, m.from_user.id))
        emo_map = {"/casino": "🎰", "/basket": "🏀", "/football": "⚽", "/dice": "🎲"}
        emo = emo_map[cmd[0]]
        
        res = bot.send_dice(m.chat.id, emoji=emo).dice.value
        time.sleep(3.5)
        
        win = amount * 10 if res in [1, 22, 43, 64] and emo == "🎰" else (int(amount * 1.8) if res >= 4 else 0)
        if win > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (win, m.from_user.id))
            bot.send_message(m.chat.id, f"🎉 Выигрыш: +{win} 🪙!")
        else: bot.send_message(m.chat.id, "💀 Проигрыш.")
        conn.commit()
    except: bot.reply_to(m, "❌ Ошибка формата ставки.")

# ==========================================
# 5. ТЕКСТОВЫЙ ОБРАБОТЧИК (РУССКИЙ)
# ==========================================
@bot.message_handler(content_types=['text'])
def text_handler(m):
    u = get_u(m)
    
    if m.text == "🤖 Нейросеть":
        ai_on(m)
    elif m.text == "🎮 Игровой зал":
        bot.send_message(m.chat.id, "Выбирай игру:", reply_markup=game_menu())
    elif m.text == "💰 Баланс":
        bot.reply_to(m, f"💰 Баланс: {u['bal']} 🪙")
    elif m.text == "👤 Кто я":
        profile_cmd(m)
    elif m.text in ["🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик"]:
        bot.reply_to(m, "Используй команду: `/casino [ставка]` (или другую)", parse_mode="Markdown")
    elif m.text == "⬅️ Назад":
        bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_menu())
    elif m.text == "➕ Добавить в чат":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Добавить", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"))
        bot.send_message(m.chat.id, "Нажми кнопку:", reply_markup=markup)
    
    # ИИ отвечает только если режим включен и это приватный чат
    elif u['mode'] == 'ai' and m.chat.type == 'private':
        threading.Thread(target=ask_ai, args=(m,)).start()

# ==========================================
# 6. ВЕБ-СЕРВЕР (ДЛЯ RENDER)
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. ULTIMATE LIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
