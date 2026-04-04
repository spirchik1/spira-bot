import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. НАСТРОЙКИ (ТОКЕН И КАНАЛ)
# ==========================================
BOT_TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
CHANNEL_ID = "@spiraofficial" # Убедись, что бот там админ!
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

def get_db():
    conn = sqlite3.connect('spira_ultimate.db', check_same_thread=False, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL') # Защита от зависаний базы
    return conn

def db_query(query, params=(), fetch=False):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()

# Создание всех таблиц с нуля
db_query('''CREATE TABLE IF NOT EXISTS users 
    (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER, ref_id INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')

# Добавляем стандартный промокод
try: db_query("INSERT INTO promo VALUES ('NEWBOT', 5000, 100, 0)")
except: pass

# ==========================================
# 2. ЛОГИКА ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
def get_u(m):
    uid = m.from_user.id
    res = db_query("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,), True)
    if not res:
        # Реферальная система
        ref = None
        if hasattr(m, 'text') and "/start" in m.text and len(m.text.split()) > 1:
            ref = m.text.split()[1]
        
        db_query("INSERT INTO users VALUES (?, ?, 1000, 'off', 'Новичок 🛡', ?, ?)", (uid, m.from_user.first_name, int(time.time()), ref))
        if ref and int(ref) != uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try: bot.send_message(ref, "👥 У вас новый реферал! +5000 🪙")
            except: pass
        return {"bal": 1000, "mode": "off", "prefix": "Новичок 🛡", "age": 0}
    return {"bal": res[0][0], "mode": res[0][1], "prefix": res[0][2], "age": int(time.time()) - res[0][3]}

def is_sub(uid):
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        return status in ['member', 'administrator', 'creator']
    except: return True # Если ошибка доступа к каналу - пускаем, чтобы бот не вис

# ==========================================
# 3. КЛАВИАТУРЫ (ГЛАВНЫЕ)
# ==========================================
def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "👤 Профиль")
    markup.add("🛒 Магазин", "🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод")
    return markup

# ==========================================
# 4. ИГРОВОЙ ДВИЖОК (8+ ИГР)
# ==========================================
GAMES = {
    "🎰 Казино": "casino", "🎲 Кубик": "dice", "🪙 Монетка": "coin", 
    "🎯 Дартс": "darts", "🎳 Боулинг": "bowling", "⚽ Футбол": "football", 
    "🏀 Баскет": "basket", "🎰 Слоты": "slots"
}

@bot.message_handler(func=lambda m: m.text == "🎮 Игровой зал")
def game_hall(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.add(*list(GAMES.keys()), "⬅️ Назад")
    bot.send_message(m.chat.id, "🕹 Выбери игру:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in GAMES.keys())
def ask_bet(m):
    game_id = GAMES[m.text]
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(*[types.InlineKeyboardButton(f"{a} 🪙", callback_data=f"go_{game_id}_{a}") for a in [250, 500, 1000, 5000]])
    bot.send_message(m.chat.id, f"🎰 **{m.text}**\nВыбери ставку или введите `/{game_id} [сумма]`:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("go_"))
def callback_game(c):
    _, g, amt = c.data.split("_")
    run_game_logic(c.message, g, int(amt), c.from_user.id)

def run_game_logic(m, game, bet, uid):
    u = get_u(m)
    if u['bal'] < bet: return bot.send_message(m.chat.id, "❌ Недостаточно 🪙 на балансе!")
    
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    msg = bot.send_message(m.chat.id, f"🎲 Ставка принята! Крутим...")
    
    win, coeff = False, 2.0
    if game in ["dice", "darts", "bowling", "football", "basket"]:
        emo = {"dice":"🎲", "darts":"🎯", "bowling":"🎳", "football":"⚽", "basket":"🏀"}[game]
        res = bot.send_dice(m.chat.id, emo).dice.value
        time.sleep(3)
        if res >= 4: win = True
    elif game == "coin":
        win = random.choice([True, False])
        bot.send_message(m.chat.id, "🪙 Результат: " + ("ОРЕЛ (Победа!)" if win else "РЕШКА (Проигрыш)"))
    elif game in ["casino", "slots"]:
        res = bot.send_dice(m.chat.id, "🎰").dice.value
        time.sleep(4)
        if res in [1, 22, 43, 64]: win, coeff = True, 10.0
        
    if win:
        prize = int(bet * coeff)
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
        bot.send_message(m.chat.id, f"🏆 ПОБЕДА! Твой выигрыш: {prize} 🪙")
    else:
        bot.send_message(m.chat.id, "📉 Увы, это проигрыш. Попробуй еще раз!")

# ==========================================
# 5. НЕЙРОСЕТЬ S.P.I.R.A. (ТОЛЬКО РУССКИЙ)
# ==========================================
def ask_ai(m):
    try:
        prompt = f"Ты - S.P.I.R.A., созданная разработчиком Spirchik. Твой ответ должен быть только на русском языке. Будь полезной и краткой."
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_35_turbo,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": m.text}]
        )
        bot.reply_to(m, response if response else "📡 Сигнал потерян...")
    except: bot.reply_to(m, "⚠️ Ошибка ИИ. Попробуй позже.")

# ==========================================
# 6. ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ
# ==========================================
@bot.message_handler(commands=['start'])
def start_bot(m):
    get_u(m)
    if not is_sub(m.from_user.id):
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔗 Подписаться", url=f"https://t.me/{CHANNEL_ID[1:]}"))
        return bot.send_message(m.chat.id, "❌ Чтобы пользоваться ботом, подпишись на наш канал!", reply_markup=kb)
    bot.send_message(m.chat.id, "🦾 **S.P.I.R.A. v17.0 готова к работе!**\nРазработчик: Spirchik", reply_markup=main_kb(), parse_mode="Markdown")

@bot.message_handler(content_types=['text'])
def global_logic(m):
    u = get_u(m)
    
    # Режимы ИИ
    if m.text == "🤖 Нейросеть":
        db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "📡 Режим ИИ включен. Задавай вопрос!", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))
        return

    if m.text == "🛑 Стоп" or m.text == "⬅️ Назад":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "🏠 Возврат в меню.", reply_markup=main_kb())
        return

    if u['mode'] == 'ai':
        threading.Thread(target=ask_ai, args=(m,)).start()
        return

    # Функции меню
    if m.text == "💰 Баланс":
        bot.reply_to(m, f"💳 Твой счет: {u['bal']} 🪙")
    
    elif m.text == "👤 Профиль":
        bot.reply_to(m, f"👤 **ПРОФИЛЬ**\n\nИмя: {m.from_user.first_name}\nСтатус: {u['prefix']}\nБаланс: {u['bal']} 🪙", parse_mode="Markdown")

    elif m.text == "🎟 Промокод":
        msg = bot.send_message(m.chat.id, "⌨️ Введите промокод (например, NEWBOT):")
        bot.register_next_step_handler(msg, apply_promo)

    elif m.text == "🏆 ТОП":
        res = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 5", fetch=True)
        top_msg = "🏆 **ТОП-5 БОГАЧЕЙ:**\n\n"
        for i, row in enumerate(res): top_msg += f"{i+1}. {row[0]} — {row[1]} 🪙\n"
        bot.send_message(m.chat.id, top_msg, parse_mode="Markdown")

def apply_promo(m):
    code = m.text.upper()
    res = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)
    if res and res[0][2] < res[0][1]:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (res[0][0], m.from_user.id))
        db_query("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
        bot.reply_to(m, f"✅ Успех! Получено {res[0][0]} 🪙")
    else: bot.reply_to(m, "❌ Код неверен или закончился.")

# ==========================================
# 7. ВЕБ-СЕРВЕР ДЛЯ RENDER
# ==========================================
app = Flask(__name__)
@app.route('/')
def index(): return "S.P.I.R.A. v17.0 ALIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling(timeout=60)
