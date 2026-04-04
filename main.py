import os, time, threading, sqlite3, re, telebot
from telebot import types
from flask import Flask
from g4f.client import Client

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
BOT_TOKEN = "8632196470:AAFTx66ffHExh8KDUwLzZ-f94DhQKXweBmA"
BOT_USERNAME = "spiraaiofficial_bot" 
bot = telebot.TeleBot(BOT_TOKEN)
ai_client = Client()

SYSTEM_PROMPT = "Ты S.P.I.R.A., продвинутый игровой ИИ. Твой создатель — spirchik. Отвечай кратко."

# БАЗА ДАННЫХ
conn = sqlite3.connect('spira_final_v5.db', check_same_thread=False)
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
# 2. ФУНКЦИЯ АВТО-АДМИНКИ (ПРЕФИКСЫ В ЧАТЕ)
# ==========================================
def apply_group_prefix(m, prefix):
    if m.chat.type in ['group', 'supergroup']:
        try:
            # Даем пустую админку (все права False)
            bot.promote_chat_member(m.chat.id, m.from_user.id, 
                can_manage_chat=False, can_post_messages=False, can_edit_messages=False, 
                can_delete_messages=False, can_manage_video_chats=False, can_restrict_members=False, 
                can_promote_members=False, can_change_info=False, can_invite_users=False, 
                can_pin_messages=False)
            
            # Устанавливаем текст префикса
            bot.set_chat_administrator_custom_title(m.chat.id, m.from_user.id, prefix)
        except Exception as e:
            # Если бот не админ или юзер - владелец чата, Телеграм выдаст ошибку, просто игнорируем
            pass

# ==========================================
# 3. МЕНЮ
# ==========================================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал")
    markup.add("💰 Баланс", "🏆 ТОП", "🛒 Магазин")
    markup.add("👤 Кто я", "➕ Добавить в чат")
    return markup

def game_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик")
    markup.add("⬅️ Назад")
    return markup

def bet_inline(game):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("100 🪙", callback_data=f"b_{game}_100"),
               types.InlineKeyboardButton("500 🪙", callback_data=f"b_{game}_500"))
    markup.add(types.InlineKeyboardButton("1000 🪙", callback_data=f"b_{game}_1000"),
               types.InlineKeyboardButton("ВСЁ НА КОН! 🔥", callback_data=f"b_{game}_all"))
    return markup

# ==========================================
# 4. ОБРАБОТЧИКИ
# ==========================================
@bot.message_handler(commands=['start'])
def st(m):
    u = get_u(m)
    apply_group_prefix(m, u['prefix'])
    bot.send_message(m.chat.id, "🤖 **S.P.I.R.A. v5.0**\n\nСистема авто-префиксов активирована.", reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Кто я")
def profile(m):
    u = get_u(m)
    apply_group_prefix(m, u['prefix'])
    text = (f"👤 **ТЕХНО-ПРОФИЛЬ:**\n\n"
            f"🏷 Статус: **{u['prefix']}**\n"
            f"💰 Баланс: **{u['bal']} 🪙**\n"
            f"🛠 Создатель: spirchik")
    bot.reply_to(m, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop(m):
    text = ("🛒 **МАГАЗИН ПРЕФИКСОВ**\n\n"
            "1. [👑 Олигарх] — 50,000 🪙\n"
            "2. [⚡️ Киберпанк] — 15,000 🪙\n"
            "3. [🥷 Фантом] — 5,000 🪙\n"
            "4. [💎 VIP] — 2,000 🪙\n\n"
            "Купи и он появится в профиле и над именем в чате!")
    bot.send_message(m.chat.id, text)

@bot.message_handler(func=lambda m: m.text.lower().startswith("купить "))
def buying(m):
    u = get_u(m)
    try:
        c = m.text.split()[-1]
        items = {"1": ("👑 Олигарх", 50000), "2": ("⚡️ Киберпанк", 15000), "3": ("🥷 Фантом", 5000), "4": ("💎 VIP", 2000)}
        if c in items:
            name, price = items[c]
            if u['bal'] >= price:
                cursor.execute("UPDATE users SET balance = balance - ?, prefix = ? WHERE id=?", (price, name, m.from_user.id))
                conn.commit()
                bot.reply_to(m, f"✅ Теперь ты **{name}**!")
                apply_group_prefix(m, name) # Сразу обновляем в чате
            else: bot.reply_to(m, "❌ Монет не хватает.")
    except: pass

@bot.message_handler(func=lambda m: m.text == "➕ Добавить в чат")
def add_chat(m):
    markup = types.InlineKeyboardMarkup()
    url = f"https://t.me/{BOT_USERNAME}?startgroup=true&admin=post_messages+edit_messages+delete_messages+restrict_members+promote_members+pin_messages+invite_users"
    markup.add(types.InlineKeyboardButton("🚀 Установить в чат", url=url))
    bot.send_message(m.chat.id, "Нажми кнопку, чтобы добавить меня в чат с правами админа для работы префиксов!", reply_markup=markup)

@bot.message_handler(content_types=['text'])
def global_handler(m):
    u = get_u(m)
    
    # АВТО-ПРЕФИКС ПРИ КАЖДОМ СООБЩЕНИИ В ГРУППЕ
    apply_group_prefix(m, u['prefix'])

    if m.text == "🎮 Игровой зал": bot.send_message(m.chat.id, "Игры:", reply_markup=game_menu())
    elif m.text == "🤖 Нейросеть":
        cursor.execute("UPDATE users SET mode='ai' WHERE id=?"); conn.commit()
        bot.send_message(m.chat.id, "📡 ИИ включен.")
    elif m.text == "⬅️ Назад": bot.send_message(m.chat.id, "Меню:", reply_markup=main_menu())
    elif m.text in ["🎰 Казино", "🏀 Баскет", "⚽ Футбол", "🎲 Кубик"]:
        bot.send_message(m.chat.id, f"Ставка для {m.text}:", reply_markup=bet_inline(m.text))
    elif u['mode'] == 'ai' and m.chat.type == 'private':
        try:
            r = ai_client.chat.completions.create(model="gpt-4o", messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":m.text}])
            bot.reply_to(m, r.choices[0].message.content)
        except: bot.reply_to(m, "📡 Ядро ИИ спит.")

# ==========================================
# 5. ЗАПУСК
# ==========================================
app = Flask(__name__)
@app.route('/')
def h(): return "S.P.I.R.A. PREFIX SYSTEM LIVE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling()
