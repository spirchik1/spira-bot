import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHrho4RdT6jya9HktGoLgG4zxACKvWfP_I"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=35)

def get_db():
    return sqlite3.connect('spira_final_v12.db', check_same_thread=False)

conn = get_db()
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER, bonus_prefix TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, loses INTEGER, math_wins INTEGER)''')

# Инициализация промокода NEWBOT
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
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)", (uid, m.from_user.first_name, 1000, "off", "Новичок 🛡", now))
        cursor.execute("INSERT INTO stats VALUES (?, ?, ?)", (uid, 0, 0))
        conn.commit()
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": row[0], "mode": row[1], "prefix": row[2], "age": int(time.time()) - row[3]}

def is_sub(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return False

# ==========================================
# 2. МЕНЮ И ИНТЕРФЕЙС
# ==========================================
def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игровой зал")
    m.add("💰 Баланс", "🏆 ТОП", "👤 Профиль", "🛒 Магазин")
    m.add("🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    return m

# ==========================================
# 3. ЛОГИКА ИГР НА СКИЛЛ
# ==========================================
active_math = {}

def start_math(m):
    a, b = random.randint(10, 99), random.randint(10, 99)
    active_math[m.from_user.id] = a + b
    bot.send_message(m.chat.id, f"🧠 **МАТЕМАТИКА:**\nСколько будет {a} + {b}?\nУ тебя 15 секунд!")

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================
@bot.message_handler(commands=['start'])
def welcome(m):
    if not is_sub(m.from_user.id):
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Подписаться", url="https://t.me/spiraofficial"))
        return bot.send_message(m.chat.id, "❌ **Доступ заблокирован!**\nПодпишись на канал, чтобы войти в систему.", reply_markup=markup)
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. v12.5 Активирована**", reply_markup=main_menu())

@bot.message_handler(commands=['promo'])
def promo_handler(m):
    u = get_u(m)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "Используй: `/promo NEWBOT`", parse_mode="Markdown")
    code = p[1].upper()
    cursor.execute("SELECT reward, limit_uses, used_count, bonus_prefix FROM promo WHERE code=?", (code,))
    row = cursor.fetchone()
    if row and row[2] < row[1]:
        cursor.execute("UPDATE users SET balance = balance + ?, prefix = ? WHERE id=?", (row[0], row[3], m.from_user.id))
        cursor.execute("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
        conn.commit()
        bot.reply_to(m, f"✅ **Код принят!**\nБонус: +{row[0]} 🪙\nНовый статус: {row[3]}")
    else: bot.reply_to(m, "❌ Код недействителен.")

@bot.message_handler(func=lambda m: m.text == "🎯 Задания")
def show_tasks(m):
    u = get_u(m)
    cursor.execute("SELECT loses, math_wins FROM stats WHERE user_id=?", (m.from_user.id,))
    st_row = cursor.fetchone()
    
    # Визуализация заданий
    task1 = "✅ Выполнено" if u['age'] > 2592000 else f"⏳ Еще {30 - u['age']//86400} дн."
    task2 = "✅ Выполнено" if st_row[0] >= 10 else f"⏳ Прогресс: {st_row[0]}/10"
    
    msg = (
        "🎯 **СПИСОК ЗАДАНИЙ:**\n\n"
        f"1. **Старичок** (30 дней в игре)\nСтатус: {task1} | Награда: 50,000 🪙\n\n"
        f"2. **Лудоман** (10 проигрышей)\nСтатус: {task2} | Награда: Статус [🎰 Азартный]\n\n"
        "Награды начисляются автоматически при достижении цели."
    )
    bot.send_message(m.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎒 Инвентарь")
def inventory_handler(m):
    cursor.execute("SELECT item FROM inventory WHERE user_id=?", (m.from_user.id,))
    items = cursor.fetchall()
    if not items: return bot.reply_to(m, "📭 Твой инвентарь пока пуст.")
    
    text = "🎒 **ТВОИ ПРЕДМЕТЫ:**\n\n"
    markup = types.InlineKeyboardMarkup()
    for it in items:
        text += f"🔹 {it[0]}\n"
        markup.add(types.InlineKeyboardButton(f"Надеть {it[0]}", callback_data=f"set_pre_{it[0]}"))
    bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_pre_"))
def set_prefix_callback(call):
    new_p = call.data.replace("set_pre_", "")
    cursor.execute("UPDATE users SET prefix = ? WHERE id=?", (new_p, call.from_user.id))
    conn.commit()
    bot.answer_callback_query(call.id, f"Префикс {new_p} надет!")

@bot.message_handler(content_types=['text'])
def global_logic(m):
    if not is_sub(m.from_user.id): return welcome(m)
    u = get_u(m)
    
    # Обработка математической игры
    if m.from_user.id in active_math:
        if m.text == str(active_math[m.from_user.id]):
            cursor.execute("UPDATE users SET balance = balance + 2000 WHERE id=?", (m.from_user.id,))
            cursor.execute("UPDATE stats SET math_wins = math_wins + 1 WHERE user_id=?", (m.from_user.id,))
            conn.commit()
            bot.reply_to(m, "✅ **Верно!** +2000 🪙 в твой кошелек.")
        else: bot.reply_to(m, "❌ Ошибочка. Тренируй мозг!")
        del active_math[m.from_user.id]
        return

    if m.text == "🎮 Игровой зал":
        km = types.ReplyKeyboardMarkup(resize_keyboard=True)
        km.add("🧮 Математика", "🎰 Казино", "⬅️ Назад")
        bot.send_message(m.chat.id, "Выбери испытание:", reply_markup=km)
    
    elif m.text == "🧮 Математика":
        start_math(m)
    
    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "📡 Режим ИИ активен. Пиши сообщение.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Выйти"))

    elif m.text == "🛑 Выйти" or m.text == "⬅️ Назад":
        cursor.execute("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "Возврат в главное меню.", reply_markup=main_menu())

    elif u['mode'] == 'ai' and m.chat.type == 'private':
        threading.Thread(target=lambda: bot.reply_to(m, g4f.ChatCompletion.create(model=g4f.models.gpt_35_turbo, messages=[{"role":"user","content":m.text}]))).start()

# ==========================================
# 5. СЕРВЕРНАЯ ЧАСТЬ
# ==========================================
app = Flask(__name__)
@app.route('/')
def health(): return "S.P.I.R.A. v12.5 ACTIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
