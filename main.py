import os, time, threading, sqlite3, re, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHZ_i8u_765zDxj36hCWSeKUSYr-9RYZvY"
CHANNEL_ID = "@spiraofficial"  # ID канала для проверки подписки
CHANNEL_URL = "https://t.me/spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=20)

SYSTEM_PROMPT = "Ты S.P.I.R.A., игровой ИИ. Твой создатель — spirchik. Отвечай кратко."

# БАЗА ДАННЫХ
def get_db_connection():
    return sqlite3.connect('spira_v10.db', check_same_thread=False)

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
# 2. ПРОВЕРКА ПОДСПИСКИ
# ==========================================
def is_subscribed(user_id):
    try:
        status = bot.get_chat_member(CHANNEL_ID, user_id).status
        return status in ['member', 'administrator', 'creator']
    except:
        return False

def check_sub_decorator(func):
    def wrapper(m):
        if not is_subscribed(m.from_user.id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_URL))
            return bot.send_message(m.chat.id, "❌ **Доступ ограничен!**\nЧтобы пользоваться ботом, подпишись на наш канал.", reply_markup=markup, parse_mode="Markdown")
        return func(m)
    return wrapper

# ==========================================
# 3. МЕНЮ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "🏆 ТОП")
    markup.add("👤 Кто я", "🛒 Магазин")
    return markup

def bet_menu(game_cmd):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"{game_cmd} 100", f"{game_cmd} 500")
    markup.add(f"{game_cmd} 1000", "⬅️ Назад")
    return markup

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================

@bot.message_handler(commands=['start', 'help'])
@check_sub_decorator
def st(m):
    get_u(m)
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. v10.0 Активирована**\nИспользуй меню или команды /ai, /stop, /top.", reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@check_sub_decorator
def top_players(m):
    cursor.execute("SELECT name, balance, prefix FROM users ORDER BY balance DESC LIMIT 10")
    rows = cursor.fetchall()
    text = "🏆 **ТОП 10 БОГАТЕЕВ:**\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[2]} {row[0]} — {row[1]} 🪙\n"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['casino', 'basket', 'football', 'dice'])
@check_sub_decorator
def handle_games(m):
    u = get_u(m)
    parts = m.text.split()
    if len(parts) < 2:
        return bot.send_message(m.chat.id, f"Выбери ставку для {parts[0]}:", reply_markup=bet_menu(parts[0]))
    
    try:
        amount = int(parts[1])
        if amount <= 0: return
        if u['bal'] < amount: return bot.reply_to(m, "❌ Мало монет!")
        
        cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, m.from_user.id))
        emo_map = {"/casino": "🎰", "/basket": "🏀", "/football": "⚽", "/dice": "🎲"}
        emo = emo_map.get(parts[0], "🎲")
        
        msg = bot.send_dice(m.chat.id, emoji=emo)
        val = msg.dice.value
        time.sleep(3.5)
        
        # Логика выигрыша (Строгая)
        win = 0
        if emo == "🎰":
            if val in [1, 22, 43, 64]: win = amount * 10
        elif emo in ["🏀", "⚽"]:
            if val >= 4: win = int(amount * 1.8)
        else: # Кубик
            if val >= 4: win = int(amount * 1.5)

        if win > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (win, m.from_user.id))
            bot.send_message(m.chat.id, f"🎉 Выигрыш: +{win} 🪙!")
        else:
            bot.send_message(m.chat.id, "💀 Ты проиграл.")
        conn.commit()
    except: bot.reply_to(m, "❌ Ошибка ставки.")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
@check_sub_decorator
def shop(m):
    text = (
        "🛒 **МАГАЗИН ПРЕФИКСОВ:**\n\n"
        "1. [👑 Олигарх] — 100,000\n"
        "2. [⚡️ Киберпанк] — 50,000\n"
        "3. [💎 Алмазный] — 25,000\n"
        "4. [🥷 Фантом] — 10,000\n"
        "5. [🔥 Легенда] — 5,000\n\n"
        "Напиши: **Купить [номер]**"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text.lower().startswith("купить "))
@check_sub_decorator
def buy_item(m):
    u = get_u(m)
    items = {
        "1": ("👑 Олигарх", 100000), "2": ("⚡️ Киберпанк", 50000),
        "3": ("💎 Алмазный", 25000), "4": ("🥷 Фантом", 10000),
        "5": ("🔥 Легенда", 5000)
    }
    num = m.text.split()[-1]
    if num in items:
        name, price = items[num]
        if u['bal'] >= price:
            cursor.execute("UPDATE users SET balance = balance - ?, prefix = ? WHERE id=?", (price, name, m.from_user.id))
            conn.commit()
            bot.reply_to(m, f"✅ Куплено! Твой новый статус: **{name}**")
        else: bot.reply_to(m, "❌ Не хватает монет.")

@bot.message_handler(content_types=['text'])
@check_sub_decorator
def text_logic(m):
    u = get_u(m)
    if m.text == "🎮 Игровой зал":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик", "⬅️ Назад")
        bot.send_message(m.chat.id, "Выбирай игру:", reply_markup=markup)
    elif m.text == "🎰 Казино": bot.send_message(m.chat.id, "Выбери ставку:", reply_markup=bet_menu("/casino"))
    elif m.text == "🏀 Баскет": bot.send_message(m.chat.id, "Выбери ставку:", reply_markup=bet_menu("/basket"))
    elif m.text == "⚽ Футбол": bot.send_message(m.chat.id, "Выбери ставку:", reply_markup=bet_menu("/football"))
    elif m.text == "🎲 Кубик": bot.send_message(m.chat.id, "Выбери ставку:", reply_markup=bet_menu("/dice"))
    elif m.text == "🏆 ТОП": top_players(m)
    elif m.text == "💰 Баланс": bot.reply_to(m, f"💰 Твой счет: {u['bal']} 🪙")
    elif m.text == "👤 Кто я": bot.reply_to(m, f"👤 **ПРОФИЛЬ:**\nСтатус: {u['prefix']}\nБаланс: {u['bal']}", parse_mode="Markdown")
    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?"); conn.commit()
        bot.reply_to(m, "📡 Режим ИИ ВКЛЮЧЕН.")
    elif m.text == "⬅️ Назад": bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_menu())
    elif u['mode'] == 'ai' and m.chat.type == 'private':
        threading.Thread(target=lambda: bot.reply_to(m, g4f.ChatCompletion.create(model=g4f.models.default, messages=[{"role":"user","content":m.text}]))).start()

# ==========================================
# 5. СЕРВЕР
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. ULTIMATE LIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
