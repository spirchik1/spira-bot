import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. СИСТЕМНЫЕ НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=40)

def db_query(query, params=(), fetch=False):
    """Безопасная работа с БД (открытие/закрытие для каждого запроса)"""
    with sqlite3.connect('spira_final.db', timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()

# Инициализация таблиц
db_query('''CREATE TABLE IF NOT EXISTS users 
            (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER, ref_id INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS promo 
            (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER, bonus_prefix TEXT)''')
db_query('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
db_query('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, loses INTEGER, math_wins INTEGER)''')

try:
    db_query("INSERT INTO promo VALUES (?, ?, ?, ?, ?)", ("NEWBOT", 5000, 100, 0, "OLD💪"))
except: pass

# ==========================================
# 2. ВСПОМОГАТЕЛЬНАЯ ЛОГИКА
# ==========================================
def get_user(uid, name=None, ref_id=None):
    res = db_query("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,), True)
    if not res:
        now = int(time.time())
        db_query("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", (uid, name, 1000, "off", "Новичок 🛡", now, ref_id))
        db_query("INSERT INTO stats (user_id, loses, math_wins) VALUES (?, 0, 0)", (uid,))
        if ref_id:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref_id,))
            try: bot.send_message(ref_id, "👥 У вас новый реферал! +5000 🪙")
            except: pass
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": res[0][0], "mode": res[0][1], "prefix": res[0][2], "age": int(time.time()) - res[0][3]}

def is_sub(uid):
    try: return bot.get_chat_member(CHANNEL_ID, uid).status in ['member', 'administrator', 'creator']
    except: return True # Если бот не админ, пускаем всех, чтобы не вис

# ==========================================
# 3. КЛАВИАТУРЫ
# ==========================================
def main_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "👤 Профиль")
    m.add("🛒 Магазин", "🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    m.add("👥 Рефералы", "🏆 ТОП")
    return m

def games_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    m.add("🧮 Мат", "⚡ Реакция", "🎰 Казино", "🎲 Куб", "🪙 Монета", "🎯 Дартс", "🎳 Боулинг", "⚽ Футбол", "⬅️ Назад")
    return m

# ==========================================
# 4. ОБРАБОТЧИКИ КОМАНД
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    ref_id = None
    if len(m.text.split()) > 1: ref_id = m.text.split()[1]
    get_user(m.from_user.id, m.from_user.first_name, ref_id)
    
    if not is_sub(m.from_user.id):
        btn = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Подписаться", url="https://t.me/spiraofficial"))
        return bot.send_message(m.chat.id, "⚠️ Доступ закрыт! Подпишись на канал.", reply_markup=btn)
    
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. v14.0** запущена.\nВсе системы в норме.", reply_markup=main_kb(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def bal_cmd(m):
    u = get_user(m.from_user.id)
    bot.reply_to(m, f"💳 Твой баланс: {u['bal']} 🪙")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def ref_cmd(m):
    bot.send_message(m.chat.id, f"👥 **РЕФЕРАЛКА**\n\nПриглашай друзей и получай 5,000 🪙!\n\nТвоя ссылка:\n`https://t.me/{bot.get_me().username}?start={m.from_user.id}`", parse_mode="Markdown")

# ==========================================
# 5. МАГАЗИН И КЕЙСЫ
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop_cmd(m):
    text = "🛒 **МАГАЗИН СТАТУСОВ:**\n\n1. Олигарх — 100,000 🪙\n2. Киберпанк — 50,000 🪙\n3. Легенда — 10,000 🪙\n\nДля покупки нажми кнопку ниже:"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💎 Олигарх", callback_data="buy_100000_Олигарх"))
    kb.add(types.InlineKeyboardButton("⚙️ Киберпанк", callback_data="buy_50000_Киберпанк"))
    kb.add(types.InlineKeyboardButton("🔱 Легенда", callback_data="buy_10000_Легенда"))
    bot.send_message(m.chat.id, text, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("buy_"))
def buy_callback(c):
    _, price, name = c.data.split("_")
    u = get_user(c.from_user.id)
    if u['bal'] < int(price): return bot.answer_callback_query(c.id, "❌ Недостаточно монет!")
    db_query("UPDATE users SET balance = balance - ?, prefix = ? WHERE id=?", (price, name, c.from_user.id))
    bot.edit_message_text(f"✅ Поздравляем! Теперь ты — {name}!", c.message.chat.id, c.message.message_id)

@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def cases_cmd(m):
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔑 Открыть за 2500 🪙", callback_data="case_open"))
    bot.send_message(m.chat.id, "📦 **КЕЙС S.P.I.R.A.**\nВнутри: деньги или редкие префиксы.", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data == "case_open")
def case_logic(c):
    u = get_user(c.from_user.id)
    if u['bal'] < 2500: return bot.answer_callback_query(c.id, "❌ Мало монет!")
    db_query("UPDATE users SET balance = balance - 2500 WHERE id=?", (c.from_user.id,))
    
    res = random.choice(["💰 500", "💰 5000", "💰 15000", "🎁 ПРЕФИКС:🔥 Феникс", "🎁 ПРЕФИКС:🔱 Бог"])
    if "ПРЕФИКС" in res:
        p = res.split(":")[1]
        db_query("INSERT INTO inventory VALUES (?, ?)", (c.from_user.id, p))
        bot.send_message(c.message.chat.id, f"🔥 ВАУ! Выпал префикс: {p}. Надень его в Инвентаре!")
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (int(res.split()[1]), c.from_user.id))
        bot.send_message(c.message.chat.id, f"Выигрыш: {res}")

# ==========================================
# 6. ИГРОВОЙ ЗАЛ (8 ИГР)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎮 Игровой зал")
def hall(m): bot.send_message(m.chat.id, "Выберите игру:", reply_markup=games_kb())

@bot.message_handler(func=lambda m: m.text in ["🎲 Куб", "🎯 Дартс", "🎳 Боулинг", "⚽ Футбол"])
def emoji_game(m):
    u = get_user(m.from_user.id)
    if u['bal'] < 100: return bot.reply_to(m, "Нужно минимум 100 🪙")
    db_query("UPDATE users SET balance = balance - 100 WHERE id=?", (m.from_user.id,))
    emo = {"🎲 Куб":"🎲", "🎯 Дартс":"🎯", "🎳 Боулинг":"🎳", "⚽ Футбол":"⚽"}[m.text]
    res = bot.send_dice(m.chat.id, emo).dice.value
    time.sleep(3)
    if res >= 4:
        db_query("UPDATE users SET balance = balance + 250 WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "🎉 Победа! +250 🪙")
    else: bot.send_message(m.chat.id, "💀 Проигрыш.")

@bot.message_handler(func=lambda m: m.text == "🧮 Мат")
def math_start(m):
    a, b = random.randint(1, 50), random.randint(1, 50)
    msg = bot.send_message(m.chat.id, f"Сколько будет {a} + {b}?")
    bot.register_next_step_handler(msg, lambda ms: math_check(ms, a+b))

def math_check(m, res):
    if m.text == str(res):
        db_query("UPDATE users SET balance = balance + 200 WHERE id=?", (m.from_user.id,))
        bot.reply_to(m, "✅ Верно! +200 🪙")
    else: bot.reply_to(m, f"❌ Нет. Ответ был: {res}")

# ==========================================
# 7. НЕЙРОСЕТЬ (ОПТИМИЗИРОВАННАЯ)
# ==========================================
def ai_worker(m):
    try:
        response = g4f.ChatCompletion.create(model=g4f.models.default, messages=[{"role": "user", "content": m.text}])
        bot.reply_to(m, response if response else "📡 Ядро молчит...")
    except: bot.reply_to(m, "⚠️ Ядро перегружено, но игры работают!")

@bot.message_handler(content_types=['text'])
def logic(m):
    u = get_user(m.from_user.id)
    if m.text == "🤖 Нейросеть":
        db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "📡 Режим ИИ ВКЛЮЧЕН.", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))
    elif m.text == "🛑 Стоп" or m.text == "⬅️ Назад":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "Выход в меню...", reply_markup=main_kb())
    elif u['mode'] == 'ai':
        threading.Thread(target=ai_worker, args=(m,)).start()
    elif m.text == "👤 Профиль":
        bot.reply_to(m, f"👤 **{m.from_user.first_name}**\nПрефикс: {u['prefix']}\nБаланс: {u['bal']} 🪙", parse_mode="Markdown")

# ==========================================
# 8. ЗАПУСК (RENDER)
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. v14 ACTIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
