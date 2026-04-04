import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHZ_i8u_765zDxj36hCWSeKUSYr-9RYZvY"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=30)

def get_db_connection():
    return sqlite3.connect('spira_v12.db', check_same_thread=False)

conn = get_db_connection()
cursor = conn.cursor()
# Таблицы: пользователи, промокоды, инвентарь, статистика заданий
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER, bonus_prefix TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, lose_streak INTEGER, games_played INTEGER, tasks_done TEXT)''')
# Создаем дефолтный промокод
try:
    cursor.execute("INSERT INTO promo VALUES (?, ?, ?, ?, ?)", ("NEWBOT", 5000, 100, 0, "OLD💪"))
except: pass
conn.commit()

# ==========================================
# ЛОГИКА ДАННЫХ
# ==========================================
def get_u(m):
    uid = m.from_user.id
    cursor.execute("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        now = int(time.time())
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (uid, m.from_user.first_name, 1000, "off", "Новичок 🛡", now))
        cursor.execute("INSERT INTO stats VALUES (?, ?, ?, ?)", (uid, 0, 0, ""))
        conn.commit()
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": row[0], "mode": row[1], "prefix": row[2], "age": int(time.time()) - row[3]}

def is_sub(uid):
    try: return bot.get_chat_member(CHANNEL_ID, uid).status in ['member', 'administrator', 'creator']
    except: return False

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "🏆 ТОП", "👤 Профиль", "🛒 Магазин", "🎯 Задания", "📦 Кейсы")
    return m

# ==========================================
# ИГРЫ НА СКИНЛ (МАТЕМАТИКА)
# ==========================================
math_games = {}

@bot.message_handler(func=lambda m: m.text == "🧮 Математика")
def start_math(m):
    a, b = random.randint(10, 99), random.randint(10, 99)
    res = a + b
    math_games[m.from_user.id] = res
    bot.send_message(m.chat.id, f"Быстро! Сколько будет {a} + {b}?\n(У тебя 10 секунд)")
    threading.Timer(10, check_math_timeout, [m, res]).start()

def check_math_timeout(m, res):
    if m.from_user.id in math_games and math_games[m.from_user.id] == res:
        del math_games[m.from_user.id]
        bot.send_message(m.chat.id, "⏰ Время вышло! Ты не успел.")

# ==========================================
# ПРОМОКОДЫ
# ==========================================
@bot.message_handler(commands=['promo'])
def use_promo(m):
    u = get_u(m)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "Пиши: /promo [код]")
    code = p[1].upper()
    cursor.execute("SELECT reward, limit_uses, used_count, bonus_prefix FROM promo WHERE code=?", (code,))
    row = cursor.fetchone()
    if row and row[2] < row[1]:
        cursor.execute("UPDATE users SET balance = balance + ?, prefix = ? WHERE id=?", (row[0], row[3], m.from_user.id))
        cursor.execute("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
        conn.commit()
        bot.reply_to(m, f"✅ Активировано! +{row[0]} 🪙 и статус {row[3]}")
    else: bot.reply_to(m, "❌ Код неверный или закончился.")

# ==========================================
# ЗАДАНИЯ И ДОСТИЖЕНИЯ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎯 Задания")
def tasks(m):
    u = get_u(m)
    cursor.execute("SELECT lose_streak, games_played FROM stats WHERE user_id=?", (m.from_user.id,))
    s = cursor.fetchone()
    
    t1 = "✅ Выполнено" if u['age'] > 2592000 else "⏳ В процессе" # 30 дней
    t2 = "✅ Выполнено" if s[0] >= 10 else "⏳ В процессе"
    
    text = (
        "🎯 **ВАШИ ДОСТИЖЕНИЯ:**\n\n"
        f"👴 **Старичок** (30 дней в игре)\nСтатус: {t1} | Награда: 50,000\n\n"
        f"😵‍💫 **Лудоман** (10 проигрышей подряд)\nСтатус: {t2} | Награда: Статус [🎰 Азартный]"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

# ==========================================
# КЕЙСЫ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def cases(m):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Открыть Кибер-Кейс (5000 🪙)", callback_data="open_case"))
    bot.send_message(m.chat.id, "📦 **ДОСТУПНЫЕ КЕЙСЫ:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "open_case")
def open_case(call):
    u = get_u(call)
    if u['bal'] < 5000: return bot.answer_callback_query(call.id, "Недостаточно монет!")
    
    cursor.execute("UPDATE users SET balance = balance - 5000 WHERE id=?", (call.from_user.id,))
    prize = random.choice(["1000", "10000", "25000", "PREFIX:🔥 Призрачный"])
    
    if "PREFIX" in prize:
        pref = prize.split(":")[1]
        cursor.execute("INSERT INTO inventory VALUES (?, ?)", (call.from_user.id, pref))
        msg = f"🎁 ОГО! Выбит префикс: {pref}"
    else:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (int(prize), call.from_user.id))
        msg = f"💰 Выигрыш: {prize} 🪙"
    
    conn.commit()
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id)

# ==========================================
# ОСНОВНОЙ ОБРАБОТЧИК
# ==========================================
@bot.message_handler(content_types=['text'])
def global_handler(m):
    if not is_sub(m.from_user.id):
        return bot.send_message(m.chat.id, "❌ Подпишись на @spiraofficial")
    
    u = get_u(m)
    
    if m.text == "👤 Профиль":
        bot.reply_to(m, f"👤 **ПРОФИЛЬ:**\nСтатус: {u['prefix']}\nБаланс: {u['bal']} 🪙\nВ системе: {u['age']//86400} дней", parse_mode="Markdown")
    
    elif m.text == "🎮 Игровой зал":
        mm = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mm.add("🧮 Математика", "🎰 Казино", "⬅️ Назад")
        bot.send_message(m.chat.id, "Выбирай режим:", reply_markup=mm)

    elif m.from_user.id in math_games:
        if m.text == str(math_games[m.from_user.id]):
            cursor.execute("UPDATE users SET balance = balance + 2000 WHERE id=?", (m.from_user.id,))
            conn.commit()
            bot.reply_to(m, "✅ ГЕНИЙ! +2000 🪙 за скорость.")
        else: bot.reply_to(m, "❌ Ошибка! Мозги кипят?")
        del math_games[m.from_user.id]

    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "📡 ИИ готов. Пиши вопрос.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))

    elif m.text == "🛑 Стоп":
        cursor.execute("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "Режим ИИ выключен.", reply_markup=main_menu())

    elif m.text == "⬅️ Назад":
        bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu())

    elif u['mode'] == 'ai':
        threading.Thread(target=lambda: bot.reply_to(m, g4f.ChatCompletion.create(model=g4f.models.default, messages=[{"role":"user","content":m.text}]))).start()

# ==========================================
# ФЛАСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. v11 LIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
