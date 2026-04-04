import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

def get_db():
    return sqlite3.connect('spira_mega_v13.db', check_same_thread=False)

conn = get_db()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER, referrer_id INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER, bonus_prefix TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, loses INTEGER, wins INTEGER)''')

# Промокоды
try:
    cursor.execute("INSERT INTO promo VALUES (?, ?, ?, ?, ?)", ("NEWBOT", 5000, 100, 0, "OLD💪"))
    conn.commit()
except: pass

def get_u(m):
    uid = m.from_user.id
    cursor.execute("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        now = int(time.time())
        # Проверка реферала
        ref_id = None
        if hasattr(m, 'text') and m.text.startswith('/start '):
            try:
                ref_id = int(m.text.split()[1])
                if ref_id != uid:
                    cursor.execute("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref_id,))
                    bot.send_message(ref_id, "💰 У вас новый реферал! +5000 🪙")
            except: pass
        
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", (uid, m.from_user.first_name, 1000, "off", "Новичок 🛡", now, ref_id))
        cursor.execute("INSERT INTO stats VALUES (?, ?, ?)", (uid, 0, 0))
        conn.commit()
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": row[0], "mode": row[1], "prefix": row[2], "age": int(time.time()) - row[3]}

def is_sub(uid):
    try: return bot.get_chat_member(CHANNEL_ID, uid).status in ['member', 'administrator', 'creator']
    except: return False

# ==========================================
# МЕНЮ
# ==========================================
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "👤 Профиль")
    m.add("🛒 Магазин", "🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    m.add("👥 Рефералы", "🏆 ТОП")
    return m

# ==========================================
# ИГРЫ (8 МИНИ-ИГР)
# ==========================================
active_games = {}

@bot.message_handler(func=lambda m: m.text == "🎮 Игровой зал")
def game_hall(m):
    km = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    km.add("🧮 Математика", "⚡ Реакция", "🎰 Казино", "🎲 Кубик", "🪙 Монетка", "🎯 Дартс", "🎳 Боулинг", "⚽ Футбол", "⬅️ Назад")
    bot.send_message(m.chat.id, "Выбирай игру (на удачу или на скилл):", reply_markup=km)

@bot.message_handler(func=lambda m: m.text in ["🎲 Кубик", "🎯 Дартс", "🎳 Боулинг", "⚽ Футбол"])
def emoji_games(m):
    u = get_u(m)
    if u['bal'] < 100: return bot.reply_to(m, "Минимум 100 🪙")
    cursor.execute("UPDATE users SET balance = balance - 100 WHERE id=?", (m.from_user.id,))
    
    emojis = {"🎲 Кубик": "🎲", "🎯 Дартс": "🎯", "🎳 Боулинг": "🎳", "⚽ Футбол": "⚽"}
    msg = bot.send_dice(m.chat.id, emojis[m.text])
    
    # Логика выигрыша (для дартса/футбола/боулинга свои очки)
    if msg.dice.value >= 4:
        cursor.execute("UPDATE users SET balance = balance + 300 WHERE id=?", (m.from_user.id,))
        bot.reply_to(m, "🎉 Победа! +300 🪙")
    else: bot.reply_to(m, "👎 Мимо. Попробуй еще!")
    conn.commit()

@bot.message_handler(func=lambda m: m.text == "🧮 Математика")
def math_game(m):
    a, b = random.randint(10, 50), random.randint(10, 50)
    active_games[m.from_user.id] = {"res": a + b, "type": "math"}
    bot.send_message(m.chat.id, f"Сколько будет {a} + {b}?")

# ==========================================
# СИСТЕМА КЕЙСОВ И ПРОМО
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def cases(m):
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Открыть Кейс (2500 🪙)", callback_data="buy_case"))
    bot.send_message(m.chat.id, "📦 В кейсе лежат уникальные префиксы и деньги!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "buy_case")
def open_case(call):
    u = get_u(call)
    if u['bal'] < 2500: return bot.answer_callback_query(call.id, "Недостаточно монет!")
    cursor.execute("UPDATE users SET balance = balance - 2500 WHERE id=?", (call.from_user.id,))
    
    prizes = ["500", "5000", "10000", "PREF:🔥 Феникс", "PREF:🛡 Титан", "PREF:⚡ Молния"]
    prize = random.choice(prizes)
    
    if "PREF" in prize:
        item = prize.split(":")[1]
        cursor.execute("INSERT INTO inventory VALUES (?, ?)", (call.from_user.id, item))
        bot.send_message(call.message.chat.id, f"🎁 ВЫПАЛ ПРЕДМЕТ: {item}! Проверь инвентарь.")
    else:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (int(prize), call.from_user.id))
        bot.send_message(call.message.chat.id, f"💰 Выигрыш: {prize} 🪙")
    conn.commit()

# ==========================================
# РЕФЕРАЛЫ И ПРОФИЛЬ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referrals(m):
    link = f"https://t.me/{(bot.get_me().username)}?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"👥 **РЕФЕРАЛЬНАЯ СИСТЕМА**\n\nПриглашай друзей и получай **5,000 🪙** за каждого!\n\nТвоя ссылка:\n`{link}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎒 Инвентарь")
def inv(m):
    cursor.execute("SELECT item FROM inventory WHERE user_id=?", (m.from_user.id,))
    rows = cursor.fetchall()
    if not rows: return bot.reply_to(m, "Инвентарь пуст.")
    markup = types.InlineKeyboardMarkup()
    for r in rows: markup.add(types.InlineKeyboardButton(f"Надеть {r[0]}", callback_data=f"set_{r[0]}"))
    bot.send_message(m.chat.id, "Твои предметы:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def set_pref(call):
    p = call.data.split("_")[1]
    cursor.execute("UPDATE users SET prefix = ? WHERE id=?", (p, call.from_user.id))
    conn.commit()
    bot.answer_callback_query(call.id, f"Установлен префикс: {p}")

# ==========================================
# ГЛОБАЛЬНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_all(m):
    if not is_sub(m.from_user.id):
        return bot.send_message(m.chat.id, "❌ Подпишись на @spiraofficial", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Подписаться", url="https://t.me/spiraofficial")))
    
    u = get_u(m)

    # Проверка ответов в играх
    if m.from_user.id in active_games:
        game = active_games[m.from_user.id]
        if m.text == str(game['res']):
            cursor.execute("UPDATE users SET balance = balance + 200 WHERE id=?", (m.from_user.id,))
            bot.reply_to(m, "✅ Верно! +200 🪙")
        else: bot.reply_to(m, "❌ Неверно.")
        del active_games[m.from_user.id]
        conn.commit()
        return

    if m.text == "👤 Профиль":
        bot.reply_to(m, f"👤 **{m.from_user.first_name}**\nПрефикс: {u['prefix']}\nБаланс: {u['bal']} 🪙", parse_mode="Markdown")
    
    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "📡 ИИ на связи. Пиши вопрос.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Выход"))

    elif m.text == "🛑 Выход" or m.text == "⬅️ Назад":
        cursor.execute("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_menu())

    elif u['mode'] == 'ai':
        threading.Thread(target=lambda: bot.reply_to(m, g4f.ChatCompletion.create(model=g4f.models.gpt_35_turbo, messages=[{"role":"user","content":m.text}]))).start()

# ==========================================
# RENDER
# ==========================================
app = Flask(__name__)
@app.route('/')
def health(): return "S.P.I.R.A. v13 MAX", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
