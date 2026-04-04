import os, time, threading, sqlite3, random, telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. SETTINGS & TOKENS
# ==========================================
BOT_TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=50)

def db_query(query, params=(), fetch=False):
    with sqlite3.connect('spira_v15.db', timeout=20) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch: return cursor.fetchall()
        conn.commit()

# Init Database
db_query('''CREATE TABLE IF NOT EXISTS users 
    (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, join_date INTEGER, ref_id INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)''')
db_query('''CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT)''')
db_query('''CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, games_played INTEGER, wins INTEGER)''')

try: db_query("INSERT INTO promo VALUES ('NEWBOT', 5000, 100, 0)")
except: pass

# ==========================================
# 2. CORE LOGIC
# ==========================================
def get_u(m):
    uid = m.from_user.id
    res = db_query("SELECT balance, mode, prefix, join_date FROM users WHERE id=?", (uid,), True)
    if not res:
        ref = m.text.split()[1] if hasattr(m, 'text') and len(m.text.split()) > 1 else None
        db_query("INSERT INTO users VALUES (?, ?, 1000, 'off', 'Newbie 🛡', ?, ?)", (uid, m.from_user.first_name, int(time.time()), ref))
        db_query("INSERT INTO stats VALUES (?, 0, 0)", (uid,))
        if ref:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try: bot.send_message(ref, "🔔 New Referral! +5000 coins.")
            except: pass
        return {"bal": 1000, "mode": "off", "prefix": "Newbie 🛡", "age": 0}
    return {"bal": res[0][0], "mode": res[0][1], "prefix": res[0][2], "age": int(time.time()) - res[0][3]}

def is_sub(uid):
    try: return bot.get_chat_member(CHANNEL_ID, uid).status in ['member', 'administrator', 'creator']
    except: return True

# ==========================================
# 3. KEYBOARDS (RUSSIAN MENU -> ENGLISH ACTION)
# ==========================================
def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🤖 Нейросеть", "🎮 Игровой зал", "💰 Баланс", "👤 Профиль")
    markup.add("🛒 Магазин", "🎯 Задания", "📦 Кейсы", "🎒 Инвентарь")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод")
    return markup

def bet_kb(game_type):
    kb = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(f"{amt}", callback_data=f"bet_{game_type}_{amt}") for amt in [200, 500, 1000, 5000]]
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("Manual: /" + game_type + " [bet]", callback_data="manual_info"))
    return kb

# ==========================================
# 4. GAMES & BETTING ENGINE
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎮 Игровой зал")
def game_hall(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    kb.add("🎰 Casino", "🎲 Dice", "🪙 Coin", "🎯 Darts", "🎳 Bowling", "⚽ Football", "🏀 Basket", "🎰 Slots", "⬅️ Назад")
    bot.send_message(m.chat.id, "Select a game to play:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["🎰 Casino", "🎲 Dice", "🪙 Coin", "🎯 Darts", "🎳 Bowling", "⚽ Football", "🏀 Basket", "🎰 Slots"])
def choose_bet(m):
    game = m.text.split()[1].lower() if " " in m.text else m.text.lower()
    bot.send_message(m.chat.id, f"🎮 **{m.text}**\nChoose your bet amount or type `/{game} [amount]`:", 
                     reply_markup=bet_kb(game), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("bet_"))
def handle_bet_btn(c):
    _, game, amount = c.data.split("_")
    process_game(c.message, game, int(amount), c.from_user.id)

def process_game(m, game, bet, uid):
    u = get_u(m) # uid logic handled inside
    if u['bal'] < bet or bet < 10:
        return bot.send_message(m.chat.id, "❌ Not enough coins or invalid bet!")
    
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    bot.send_message(m.chat.id, f"🎰 Game started! Bet: {bet}...")
    
    # Game Logic
    win = False
    coeff = 2.0
    
    if game in ["dice", "darts", "bowling", "football", "basket"]:
        emoji_map = {"dice":"🎲", "darts":"🎯", "bowling":"🎳", "football":"⚽", "basket":"🏀"}
        res = bot.send_dice(m.chat.id, emoji_map[game]).dice.value
        time.sleep(3)
        if res >= 4: win = True
    elif game == "coin":
        win = random.choice([True, False])
        bot.send_message(m.chat.id, "🪙 Flipping... it's " + ("HEADS!" if win else "TAILS!"))
    elif game == "casino" or game == "slots":
        res = bot.send_dice(m.chat.id, "🎰").dice.value
        time.sleep(3)
        if res in [1, 22, 43, 64]: win = True; coeff = 10.0
        
    if win:
        prize = int(bet * coeff)
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
        bot.send_message(m.chat.id, f"🎉 YOU WIN! +{prize} coins!")
    else:
        bot.send_message(m.chat.id, "💀 You lost your bet. Try again!")

# ==========================================
# 5. OTHER FEATURES (FIXED)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🏆 ТОП")
def top_players(m):
    res = db_query("SELECT name, balance, prefix FROM users ORDER BY balance DESC LIMIT 10", fetch=True)
    text = "🏆 **TOP 10 RICH PLAYERS:**\n\n"
    for i, r in enumerate(res):
        text += f"{i+1}. {r[2]} {r[0]} — {r[1]} 🪙\n"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎒 Инвентарь")
def show_inv(m):
    res = db_query("SELECT item FROM inventory WHERE user_id=?", (m.from_user.id,), True)
    if not res: return bot.reply_to(m, "Your inventory is empty.")
    kb = types.InlineKeyboardMarkup()
    for r in res: kb.add(types.InlineKeyboardButton(f"Equip {r[0]}", callback_data=f"equip_{r[0]}"))
    bot.send_message(m.chat.id, "🎒 Your Items:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎯 Задания")
def show_tasks(m):
    u = get_u(m)
    t1 = "✅" if u['age'] > 86400*7 else "❌"
    bot.send_message(m.chat.id, f"🎯 **TASKS:**\n\n1. Loyal Player (7 days): {t1}\n2. High Roller (100k balance): {'✅' if u['bal'] >= 100000 else '❌'}")

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input(m):
    msg = bot.send_message(m.chat.id, "Enter your promo code:")
    bot.register_next_step_handler(msg, process_promo)

def process_promo(m):
    code = m.text.upper()
    res = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)
    if res and res[0][2] < res[0][1]:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (res[0][0], m.from_user.id))
        db_query("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
        bot.reply_to(m, f"✅ Success! +{res[0][0]} coins.")
    else: bot.reply_to(m, "❌ Invalid or expired code.")

# ==========================================
# 6. AI PERSONALITY (SPIRA BY SPIRCHIK)
# ==========================================
def ai_logic(m):
    try:
        sys_prompt = "You are S.P.I.R.A., a smart AI created by Spirchik. Be helpful, sharp, and always mention your creator if asked."
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_35_turbo,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": m.text}]
        )
        bot.reply_to(m, response)
    except: bot.reply_to(m, "📡 System overload. Try again later.")

@bot.message_handler(content_types=['text'])
def global_h(m):
    if not is_sub(m.from_user.id): return
    u = get_u(m)
    
    if m.text == "🤖 Нейросеть":
        db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "📡 S.P.I.R.A. Online. How can I help you?", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))
    elif m.text == "🛑 Стоп" or m.text == "⬅️ Назад":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "Returning...", reply_markup=main_kb())
    elif u['mode'] == 'ai':
        threading.Thread(target=ai_logic, args=(m,)).start()
    elif m.text == "💰 Баланс":
        bot.reply_to(m, f"💳 Balance: {u['bal']} 🪙")

# ==========================================
# 7. WEB SERVER & POLLING
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. v15 STABLE", 200

if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080))), daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
