import os, time, threading, sqlite3, re, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ (ОБНОВЛЕННЫЙ ТОКЕН)
# ==========================================
BOT_TOKEN = "8632196470:AAGILk4QMOvR6BeimSxxA5aQDlUmmKt8ejc"
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
                       (uid, m.from_user.first_name, 1000, "ai", "Новичок 🛡"))
        conn.commit()
        return {"bal": 1000, "mode": "ai", "prefix": "Новичок 🛡"}
    return {"bal": row[0], "mode": row[1], "prefix": row[2]}

# ==========================================
# 2. ПРЕФИКСЫ И АДМИНКИ
# ==========================================
def apply_group_prefix(m, prefix):
    if m.chat.type in ['group', 'supergroup']:
        try:
            # Даем права (пустые), чтобы можно было поставить Custom Title
            bot.promote_chat_member(m.chat.id, m.from_user.id, can_manage_chat=False)
            bot.set_chat_administrator_custom_title(m.chat.id, m.from_user.id, prefix)
        except:
            pass # Если бот не админ или юзер — создатель чата

# ==========================================
# 3. УМНЫЙ ИИ (С ЗАЩИТОЙ ОТ ТОРМОЗОВ)
# ==========================================
def ask_ai(message):
    try:
        # Пытаемся получить ответ от GPT-4 через g4f
        response = g4f.ChatCompletion.create(
            model=g4f.models.default, # Автовыбор лучшего провайдера
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": message.text}],
        )
        if response:
            bot.reply_to(message, response)
        else:
            bot.reply_to(message, "📡 Сигнал потерян. Попробуй еще раз.")
    except Exception as e:
        bot.reply_to(message, "⚠️ Система ИИ на перезагрузке. Казино и игры работают!")

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "🏆 ТОП", "🛒 Магазин")
    markup.add("👤 Кто я", "➕ Добавить в чат")
    return markup

@bot.message_handler(commands=['start'])
def st(m):
    get_u(m)
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. Активирована**\nТокен обновлен. Протоколы защиты включены.", reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Кто я")
def profile(m):
    u = get_u(m)
    apply_group_prefix(m, u['prefix'])
    bot.reply_to(m, f"👤 **ПРОФИЛЬ:**\n\n🆔 ID: `{m.from_user.id}`\n🏷 Статус: **{u['prefix']}**\n💰 Баланс: **{u['bal']} 🪙**", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop(m):
    text = "🛒 **МАГАЗИН:**\n1. [👑 Олигарх] — 50,000\n2. [⚡️ Киберпанк] — 15,000\n3. [🥷 Фантом] — 5,000\n\nНапиши: Купить [номер]"
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text.lower().startswith("купить "))
def buy(m):
    u = get_u(m)
    prices = {"1": ("👑 Олигарх", 50000), "2": ("⚡️ Киберпанк", 15000), "3": ("🥷 Фантом", 5000)}
    choice = m.text.split()[-1]
    if choice in prices:
        name, price = prices[choice]
        if u['bal'] >= price:
            cursor.execute("UPDATE users SET balance = balance - ?, prefix = ? WHERE id=?", (price, name, m.from_user.id))
            conn.commit()
            bot.reply_to(m, f"✅ Статус **{name}** получен!")
            apply_group_prefix(m, name)
        else: bot.reply_to(m, "❌ Недостаточно монет.")

@bot.message_handler(func=lambda m: re.match(r"^(🎰 казино|🏀 баскет|⚽ футбол|🎲 кубик)\s+(\d+)$", m.text.lower()))
def bet(m):
    u = get_u(m)
    parts = m.text.split()
    amount = int(parts[1])
    if u['bal'] < amount: return bot.reply_to(m, "❌ Недостаточно баланса!")
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, m.from_user.id))
    emo = "🎰" if "казино" in parts[0].lower() else ("🏀" if "баскет" in parts[0].lower() else ("⚽" if "футбол" in parts[0].lower() else "🎲"))
    
    res = bot.send_dice(m.chat.id, emoji=emo).dice.value
    time.sleep(3.5)
    
    win = amount * 10 if res in [1, 22, 43, 64] and emo == "🎰" else (int(amount * 1.8) if res >= 4 else 0)
    if win > 0:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id=?", (win, m.from_user.id))
        bot.send_message(m.chat.id, f"🎉 Выигрыш: +{win} 🪙!")
    else: bot.send_message(m.chat.id, "💀 Проигрыш. Попробуй еще раз!")
    conn.commit()

@bot.message_handler(content_types=['text'])
def global_handler(m):
    u = get_u(m)
    apply_group_prefix(m, u['prefix'])

    if m.text == "🎮 Игровой зал":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик", "⬅️ Назад")
        bot.send_message(m.chat.id, "Выбирай игру:", reply_markup=markup)
    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?"); conn.commit()
        bot.send_message(m.chat.id, "📡 Режим ИИ включен. Спрашивай!")
    elif m.text == "⬅️ Назад":
        bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_menu())
    elif m.text == "💰 Баланс":
        bot.send_message(m.chat.id, f"💰 Ваш баланс: {u['bal']} 🪙")
    elif m.text == "➕ Добавить в чат":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Добавить", url=f"https://t.me/{BOT_USERNAME}?startgroup=true"))
        bot.send_message(m.chat.id, "Нажми кнопку ниже:", reply_markup=markup)
    elif u['mode'] == 'ai' and m.chat.type == 'private':
        threading.Thread(target=ask_ai, args=(m,)).start()

# ==========================================
# 5. ВЕБ-СЕРВЕР
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. ULTIMATE LIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
