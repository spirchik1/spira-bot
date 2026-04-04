import os, time, threading, sqlite3, re, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAHZ_i8u_765zDxj36hCWSeKUSYr-9RYZvY"
CHANNEL_ID = "@spiraofficial"
CHANNEL_URL = "https://t.me/spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=25)

SYSTEM_PROMPT = "Ты S.P.I.R.A., игровой ИИ. Твой создатель — spirchik. Отвечай кратко и по делу."

def get_db_connection():
    return sqlite3.connect('spira_v11.db', check_same_thread=False)

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
    except: return False

def check_sub(func):
    def wrapper(m):
        if not is_subscribed(m.from_user.id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📢 Подписаться", url=CHANNEL_URL))
            return bot.send_message(m.chat.id, "⚠️ **Доступ заблокирован!**\nПодпишись на канал, чтобы продолжить.", reply_markup=markup, parse_mode="Markdown")
        return func(m)
    return wrapper

# ==========================================
# 3. КЛАВИАТУРЫ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "🏆 ТОП")
    markup.add("👤 Кто я", "🛒 Магазин")
    return markup

def ai_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🛑 Остановить ИИ")
    return markup

def game_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик")
    markup.add("⬅️ Назад")
    return markup

def bet_menu(game_cmd):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(f"{game_cmd} 100", f"{game_cmd} 500", f"{game_cmd} 1000")
    markup.add("⬅️ Назад")
    return markup

# ==========================================
# 4. ЛОГИКА ИИ
# ==========================================
def ask_ai_logic(message):
    try:
        # Отправляем "печатает", чтобы юзер видел активность
        bot.send_chat_action(message.chat.id, 'typing')
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_4,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message.text}],
        )
        if response:
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "❌ Ошибка: Провайдер ИИ не ответил. Попробуй еще раз.")
    except Exception as e:
        bot.reply_to(message, "⚠️ Ядро перегружено. Попробуй задать вопрос позже.")

# ==========================================
# 5. ОБРАБОТЧИКИ
# ==========================================
@bot.message_handler(commands=['start'])
@check_sub
def start(m):
    get_u(m)
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. v10.5**\nСистема готова к работе.", reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(commands=['top'])
@check_sub
def top(m):
    cursor.execute("SELECT name, balance, prefix FROM users ORDER BY balance DESC LIMIT 10")
    rows = cursor.fetchall()
    res = "🏆 **ТОП ИГРОКОВ:**\n\n"
    for i, r in enumerate(rows, 1):
        res += f"{i}. {r[2]} {r[0]} — {r[1]} 🪙\n"
    bot.send_message(m.chat.id, res, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text.startswith(('/casino', '/basket', '/football', '/dice')))
@check_sub
def play(m):
    u = get_u(m)
    p = m.text.split()
    if len(p) < 2: return bot.reply_to(m, "Укажи ставку цифрами!")
    
    amount = int(p[1])
    if u['bal'] < amount: return bot.reply_to(m, "❌ Баланс слишком мал.")
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, m.from_user.id))
    emo = {"/casino":"🎰", "/basket":"🏀", "/football":"⚽", "/dice":"🎲"}.get(p[0], "🎲")
    
    res = bot.send_dice(m.chat.id, emoji=emo).dice.value
    time.sleep(3.5)
    
    win = 0
    if emo == "🎰" and res in [1, 22, 43, 64]: win = amount * 10
    elif emo in ["🏀", "⚽"] and res >= 4: win = int(amount * 1.8)
    elif emo == "🎲" and res >= 4: win = int(amount * 1.5)

    if win > 0:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (win, m.from_user.id))
        bot.send_message(m.chat.id, f"🎉 Победа! Выигрыш: {win} 🪙")
    else: bot.send_message(m.chat.id, "💀 Проигрыш.")
    conn.commit()

@bot.message_handler(content_types=['text'])
@check_sub
def handle_text(m):
    u = get_u(m)
    
    # ПЕРЕКЛЮЧАТЕЛИ РЕЖИМОВ
    if m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "📡 Режим ИИ включен. Жду твоих вопросов.", reply_markup=ai_menu())
    
    elif m.text == "🛑 Остановить ИИ":
        cursor.execute("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        conn.commit()
        bot.send_message(m.chat.id, "🔌 Режим ИИ выключен. Возвращаю меню.", reply_markup=main_menu())

    elif m.text == "🎮 Игровой зал":
        bot.send_message(m.chat.id, "Выбирай игру:", reply_markup=game_menu())

    elif m.text == "🎰 Казино": bot.send_message(m.chat.id, "Ставка:", reply_markup=bet_menu("/casino"))
    elif m.text == "🏀 Баскет": bot.send_message(m.chat.id, "Ставка:", reply_markup=bet_menu("/basket"))
    elif m.text == "⚽ Футбол": bot.send_message(m.chat.id, "Ставка:", reply_markup=bet_menu("/football"))
    elif m.text == "🎲 Кубик": bot.send_message(m.chat.id, "Ставка:", reply_markup=bet_menu("/dice"))
    
    elif m.text == "💰 Баланс": bot.reply_to(m, f"💰 Баланс: {u['bal']} 🪙")
    elif m.text == "🏆 ТОП": top(m)
    elif m.text == "👤 Кто я": bot.reply_to(m, f"👤 **ПРОФИЛЬ:**\nСтатус: {u['prefix']}\nСчет: {u['bal']} 🪙", parse_mode="Markdown")
    elif m.text == "🛒 Магазин":
        bot.send_message(m.chat.id, "🛒 **МАГАЗИН:**\n1. Олигарх — 100к\n2. Киберпанк — 50к\n3. Легенда — 10к\n\nПиши: Купить [номер]")
    
    elif m.text == "⬅️ Назад":
        bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_menu())

    # РАБОТА НЕЙРОСЕТИ
    elif u['mode'] == 'ai' and m.chat.type == 'private':
        threading.Thread(target=ask_ai_logic, args=(m,)).start()

# ==========================================
# 6. ВЕБ-ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. WORKING", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
