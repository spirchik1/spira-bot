import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

def get_db():
    conn = sqlite3.connect('spira_final_v16.db', timeout=20)
    conn.execute('PRAGMA journal_mode=WAL') # Режим для предотвращения зависаний
    return conn

def db_query(query, params=(), fetch=False):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()

# Инициализация
db_query('''CREATE TABLE IF NOT EXISTS users 
    (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER, ref_id INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
db_query('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, loses INTEGER, wins INTEGER)''')

try: db_query("INSERT INTO promo VALUES ('NEWBOT', 5000, 100, 0)")
except: pass

# ==========================================
# 2. ПРОВЕРКИ И ПОЛЬЗОВАТЕЛИ
# ==========================================
def get_u(m):
    uid = m.from_user.id
    res = db_query("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,), True)
    if not res:
        ref = m.text.split()[1] if hasattr(m, 'text') and len(m.text.split()) > 1 else None
        db_query("INSERT INTO users VALUES (?, ?, 1000, 'off', 'Новичок 🛡', ?, ?)", (uid, m.from_user.first_name, int(time.time()), ref))
        db_query("INSERT INTO stats VALUES (?, 0, 0)", (uid,))
        if ref and int(ref) != uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try: bot.send_message(ref, "👥 У вас новый реферал! +5000 🪙")
            except: pass
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": res[0][0], "mode": res[0][1], "prefix": res[0][2], "age": int(time.time()) - res[0][3]}

def is_sub(uid):
    try:
        s = bot.get_chat_member(CHANNEL_ID, uid).status
        return s in ['member', 'administrator', 'creator']
    except: return True

# ==========================================
# 3. МЕНЮ
# ==========================================
def main_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "👤 Профиль")
    m.add("🛒 Магазин", "🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    m.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод")
    return m

# ==========================================
# 4. ИГРЫ И СТАВКИ (РУССКОЕ МЕНЮ -> ENGLISH LOGIC)
# ==========================================
games_list = {
    "🎰 Casino": "casino", "🎲 Dice": "dice", "🪙 Coin": "coin", 
    "🎯 Darts": "darts", "🎳 Bowling": "bowling", "⚽ Football": "football", 
    "🏀 Basket": "basket", "🎰 Slots": "slots"
}

@bot.message_handler(func=lambda m: m.text == "🎮 Игровой зал")
def hall(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.add(*list(games_list.keys()), "⬅️ Назад")
    bot.send_message(m.chat.id, "Выберите игру:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in games_list.keys())
def bet_choice(m):
    game = games_list[m.text]
    kb = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(f"{amt}", callback_data=f"play_{game}_{amt}") for amt in [200, 500, 1000, 5000]]
    kb.add(*btns)
    bot.send_message(m.chat.id, f"🎮 **{m.text}**\nВыберите ставку или введите `/{game} [сумма]`:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("play_"))
def handle_play(c):
    _, game, amount = c.data.split("_")
    start_game(c.message, game, int(amount), c.from_user.id)

def start_game(m, game, bet, uid):
    u = get_u(m)
    if u['bal'] < bet or bet < 10:
        return bot.send_message(m.chat.id, "❌ Недостаточно средств или некорректная ставка!")
    
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    bot.send_message(m.chat.id, f"🚀 Игра начата! Ставка: {bet} 🪙")
    
    win, coeff = False, 2.0
    if game in ["dice", "darts", "bowling", "football", "basket"]:
        emo = {"dice":"🎲", "darts":"🎯", "bowling":"🎳", "football":"⚽", "basket":"🏀"}[game]
        res = bot.send_dice(m.chat.id, emo).dice.value
        time.sleep(3)
        if res >= 4: win = True
    elif game == "coin":
        win = random.choice([True, False])
        bot.send_message(m.chat.id, "🪙 Выпал " + ("ОРЕЛ!" if win else "РЕШКА!"))
    elif game in ["casino", "slots"]:
        res = bot.send_dice(m.chat.id, "🎰").dice.value
        time.sleep(3)
        if res in [1, 22, 43, 64]: win = True; coeff = 10.0
        
    if win:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (int(bet*coeff), uid))
        bot.send_message(m.chat.id, f"🎉 ПОБЕДА! +{int(bet*coeff)} 🪙")
    else: bot.send_message(m.chat.id, "💀 Проигрыш. Повезет в следующий раз!")

# ==========================================
# 5. ИИ ПЕРСОНАЛИЗАЦИЯ (STRICT RUSSIAN)
# ==========================================
def ai_call(m):
    try:
        sys_msg = "Ты — S.P.I.R.A., продвинутый ИИ, созданный разработчиком Spirchik. Твой язык — русский. Отвечай кратко, остроумно и только на русском."
        res = g4f.ChatCompletion.create(
            model=g4f.models.gpt_35_turbo,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": m.text}]
        )
        bot.reply_to(m, res if res else "📡 Мозг S.P.I.R.A. временно недоступен.")
    except: bot.reply_to(m, "⚠️ Ошибка связи с ядром.")

# ==========================================
# 6. ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ
# ==========================================
@bot.message_handler(commands=['start'])
def st(m):
    get_u(m)
    if not is_sub(m.from_user.id):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("📢 Подписаться", url="https://t.me/spiraofficial"))
        return bot.send_message(m.chat.id, "❌ Доступ ограничен! Подпишись на канал.", reply_markup=kb)
    bot.send_message(m.chat.id, "🤖 S.P.I.R.A. v16.0 ONLINE\nСоздатель: Spirchik", reply_markup=main_kb())

@bot.message_handler(func=lambda m: m.text == "🤖 Нейросеть")
def ai_mode(m):
    db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
    bot.send_message(m.chat.id, "📡 Слушаю тебя, человек. (Пиши вопрос)", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))

@bot.message_handler(content_types=['text'])
def handle_text(m):
    u = get_u(m)
    if m.text == "🛑 Стоп" or m.text == "⬅️ Назад":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        return bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb())
    
    if u['mode'] == 'ai':
        threading.Thread(target=ai_call, args=(m,)).start()
    elif m.text == "💰 Баланс": bot.reply_to(m, f"💳 Баланс: {u['bal']} 🪙")
    elif m.text == "👤 Профиль": bot.reply_to(m, f"👤 {m.from_user.first_name}\nСтатус: {u['prefix']}\nВ игре: {u['age']//86400} дн.")
    elif m.text == "🎟 Промокод":
        msg = bot.send_message(m.chat.id, "Введите промокод:")
        bot.register_next_step_handler(msg, use_promo)

def use_promo(m):
    code = m.text.upper()
    res = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)
    if res and res[0][2] < res[0][1]:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (res[0][0], m.from_user.id))
        db_query("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
        bot.reply_to(m, f"✅ Активировано! +{res[0][0]} 🪙")
    else: bot.reply_to(m, "❌ Код неверный.")

# ==========================================
# 7. ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. v16 ACTIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling(timeout=30)
