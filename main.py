import os, threading, sqlite3, random, time, json, re, io, requests
from datetime import datetime, timedelta
from collections import defaultdict
import telebot
from telebot import types
from flask import Flask
from gtts import gTTS
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

# ==========================================
# 2. БАЗА ДАННЫХ
# ==========================================
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('spira_full.db', timeout=30)
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            data = cur.fetchall()
        else:
            data = []
        conn.commit()
        return data, cur.rowcount
    except Exception as e:
        print(f"DB Error: {e}")
        return [], 0
    finally:
        conn.close()

# Создание всех таблиц
db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, ref_id INTEGER, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0, daily_last TEXT, daily_streak INTEGER DEFAULT 0, lang TEXT DEFAULT 'ru')")
db_query("CREATE TABLE IF NOT EXISTS stats (user_id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0, game_dice_wins INTEGER DEFAULT 0, game_coin_wins INTEGER DEFAULT 0, game_slots_wins INTEGER DEFAULT 0, game_casino_wins INTEGER DEFAULT 0, game_poker_wins INTEGER DEFAULT 0, game_blackjack_wins INTEGER DEFAULT 0, game_wheel_wins INTEGER DEFAULT 0, game_scratch_wins INTEGER DEFAULT 0, max_win INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0)")
db_query("CREATE TABLE IF NOT EXISTS mmr (user_id INTEGER, game TEXT, mmr INTEGER DEFAULT 1000, PRIMARY KEY (user_id, game))")
db_query("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1, PRIMARY KEY (user_id, item_id))")
db_query("CREATE TABLE IF NOT EXISTS shop_items (id TEXT PRIMARY KEY, name_ru TEXT, name_en TEXT, price INTEGER, type TEXT, effect TEXT, duration INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, items TEXT)")
db_query("CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item_id TEXT, min_bid INTEGER, current_bid INTEGER, current_bidder INTEGER, end_time TEXT, status TEXT DEFAULT 'active')")
db_query("CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, leader_id INTEGER, balance INTEGER DEFAULT 0, level INTEGER DEFAULT 1, created TEXT)")
db_query("CREATE TABLE IF NOT EXISTS guild_members (user_id INTEGER, guild_id INTEGER, role TEXT DEFAULT 'member', PRIMARY KEY (user_id, guild_id))")
db_query("CREATE TABLE IF NOT EXISTS quests (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ru TEXT, name_en TEXT, description_ru TEXT, description_en TEXT, goal_type TEXT, goal_count INTEGER, reward_coins INTEGER, reward_exp INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS user_quests (user_id INTEGER, quest_id INTEGER, progress INTEGER DEFAULT 0, completed INTEGER DEFAULT 0, PRIMARY KEY (user_id, quest_id))")
db_query("CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, prize_pool INTEGER, participants TEXT, winner_id INTEGER, status TEXT)")

# Заполнение дефолтных данных
for item in [('boost1','Буст +20%','Win Boost +20%',5000,'boost','win_chance+20',3600)]:
    db_query("INSERT OR IGNORE INTO shop_items VALUES (?,?,?,?,?,?,?)", item)
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"boost1\",\"prob\":0.7}]')")

# ==========================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_u(uid):
    res, _ = db_query("SELECT balance, mode, prefix, level, exp, lang FROM users WHERE id=?", (uid,), True)
    if res:
        return {"bal":res[0][0],"mode":res[0][1],"prefix":res[0][2],"level":res[0][3],"exp":res[0][4],"lang":res[0][5] or "ru"}
    return None

def main_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🎮 Игры", "💰 Баланс", "👤 Профиль")
    m.add("🏆 ТОП", "📦 Кейсы", "🛒 Магазин")
    m.add("⚙️ Бонус", "📜 Задания", "🎤 TTS", "🎨 Imagine")
    m.add("🏟 Турнир", "⚔️ Аукцион", "🏛 Гильдия")
    return m

def check_sub(m):
    try:
        status = bot.get_chat_member("@spiraofficial", m.from_user.id).status
        if status in ['member','administrator','creator']: return True
    except: pass
    bot.send_message(m.chat.id, "⚠️ Подпишитесь на @spiraofficial")
    return False

# ==========================================
# 4. ОБРАБОТЧИКИ (START И ИГРЫ)
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    u = get_u(uid)
    if not u:
        db_query("INSERT INTO users (id, name, balance) VALUES (?, ?, ?)", (uid, m.from_user.first_name, 5000))
        bot.send_message(m.chat.id, "🎉 Регистрация успешна! Лови 5000 🪙", reply_markup=main_kb())
    else:
        bot.send_message(m.chat.id, "🏠 Главное меню", reply_markup=main_kb())

@bot.message_handler(commands=["dice","coin","slots","casino","poker","blackjack","wheel","scratch"])
def game_handler(m):
    if not check_sub(m): return
    uid = m.from_user.id
    u = get_u(uid)
    if not u: return bot.reply_to(m, "Напиши /start")
    
    args = m.text.split()
    if len(args)<2: return bot.reply_to(m, "Формат: /игра [ставка]")
    
    try:
        bet = int(args[1])
        if bet < 10 or u['bal'] < bet: return bot.reply_to(m, "Ошибка ставки!")
        
        game = args[0][1:].split('@')[0].lower()
        db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
        
        win, coeff = False, 2.0
        if game == "dice":
            val = bot.send_dice(m.chat.id, "🎲").dice.value
            if val >= 4: win = True
        elif game == "coin":
            win = random.choice([True, False])
            bot.send_message(m.chat.id, "🪙 Орел!" if win else "🪙 Решка!")
        elif game in ("slots","casino"):
            val = bot.send_dice(m.chat.id, "🎰").dice.value
            if val in (1, 22, 43, 64): win, coeff = True, 10.0
        elif game in ("poker","blackjack"):
            player = random.randint(1,10)+random.randint(1,10)
            dealer = random.randint(1,10)+random.randint(1,10)
            win = player > dealer
            coeff = 1.8
        elif game == "wheel":
            mult = random.choices([0,1,2,5,10], weights=[30,40,20,8,2])[0]
            win = mult > 0
            coeff = mult
        elif game == "scratch":
            sym = [random.choice(["🍒","🍋","🍊","7"]) for _ in range(3)]
            bot.send_message(m.chat.id, f"🎫 {' '.join(sym)}")
            if sym[0]==sym[1]==sym[2]:
                win = True
                coeff = 5 if sym[0]!="7" else 10
        
        if win:
            prize = int(bet * coeff)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
            bot.send_message(m.chat.id, f"✅ Выигрыш: {prize} 🪙")
        else:
            bot.send_message(m.chat.id, "❌ Проигрыш")
    except:
        bot.reply_to(m, "Введите число!")

# ==========================================
# 5. ОБРАБОТЧИКИ КНОПОК
# ==========================================
@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance_btn(m):
    u = get_u(m.from_user.id)
    if u:
        bot.reply_to(m, f"💰 Ваш баланс: {u['bal']} 🪙")
    else:
        bot.reply_to(m, "Напишите /start")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_btn(m):
    u = get_u(m.from_user.id)
    if u:
        text = f"👤 {m.from_user.first_name}\nУровень: {u['level']}\nОпыт: {u['exp']}/{u['level']*100}\nБаланс: {u['bal']} 🪙"
        bot.reply_to(m, text)
    else:
        bot.reply_to(m, "/start")

@bot.message_handler(func=lambda m: m.text == "🏆 ТОП")
def top_btn(m):
    data, _ = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 10", fetch=True)
    if data:
        msg = "🏆 ТОП-10 богачей:\n" + "\n".join([f"{i+1}. {row[0]}: {row[1]} 🪙" for i,row in enumerate(data)])
        bot.send_message(m.chat.id, msg)
    else:
        bot.send_message(m.chat.id, "Нет данных")

@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def case_btn(m):
    bot.send_message(m.chat.id, "Кейс 'Обычный кейс' - 5000 🪙\nИспользуйте /case_open case1")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop_btn(m):
    items, _ = db_query("SELECT id, name_ru, price FROM shop_items", fetch=True)
    if items:
        text = "🛒 Магазин:\n" + "\n".join([f"{n} - {p} 🪙 (купить /buy {i})" for i,n,p in items])
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Магазин пуст")

@bot.message_handler(func=lambda m: m.text == "⚙️ Бонус")
def bonus_btn(m):
    uid = m.from_user.id
    today = datetime.now().date().isoformat()
    u = get_u(uid)
    if not u:
        return bot.reply_to(m, "/start")
    last, streak = db_query("SELECT daily_last, daily_streak FROM users WHERE id=?", (uid,), True)[0]
    if last == today:
        bot.reply_to(m, "Вы уже получили бонус сегодня!")
        return
    if last == (datetime.now().date() - timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1
    bonus = min(500 + (streak-1)*100, 2000)
    db_query("UPDATE users SET balance = balance + ?, daily_last = ?, daily_streak = ? WHERE id=?", (bonus, today, streak, uid))
    bot.reply_to(m, f"✅ Ежедневный бонус: +{bonus} 🪙 (Стрик: {streak})")

@bot.message_handler(func=lambda m: m.text == "📜 Задания")
def quests_btn(m):
    bot.send_message(m.chat.id, "Задания в разработке. Скоро будут!")

@bot.message_handler(func=lambda m: m.text == "🎤 TTS")
def tts_btn(m):
    msg = bot.send_message(m.chat.id, "Напишите текст для озвучки:")
    bot.register_next_step_handler(msg, tts_cmd)

@bot.message_handler(func=lambda m: m.text == "🎨 Imagine")
def imagine_btn(m):
    msg = bot.send_message(m.chat.id, "Опишите картинку:")
    bot.register_next_step_handler(msg, imagine_cmd)

@bot.message_handler(func=lambda m: m.text == "🏟 Турнир")
def tournament_btn(m):
    bot.send_message(m.chat.id, "Турниры каждые 6 часов. /tournament для участия")

@bot.message_handler(func=lambda m: m.text == "⚔️ Аукцион")
def auction_btn(m):
    bot.send_message(m.chat.id, "Аукцион: /auction list, /auction sell, /auction bid")

@bot.message_handler(func=lambda m: m.text == "🏛 Гильдия")
def guild_btn(m):
    bot.send_message(m.chat.id, "Гильдии: /guild create, /guild join, /guild info")

# ==========================================
# 6. ДОП. ФУНКЦИИ (TTS, Imagine, и т.д.)
# ==========================================
@bot.message_handler(commands=['tts'])
def tts_cmd(m):
    text = m.text.replace("/tts ", "")
    if not text:
        if m.reply_to_message and m.reply_to_message.text:
            text = m.reply_to_message.text
        else:
            return bot.reply_to(m, "Введите текст после команды")
    try:
        tts = gTTS(text, lang='ru')
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        bot.send_voice(m.chat.id, audio)
    except Exception as e:
        bot.reply_to(m, f"Ошибка TTS: {e}")

@bot.message_handler(commands=['imagine'])
def imagine_cmd(m):
    prompt = m.text.replace("/imagine ", "")
    if not prompt:
        if m.reply_to_message and m.reply_to_message.text:
            prompt = m.reply_to_message.text
        else:
            return bot.reply_to(m, "Опишите картинку")
    bot.send_message(m.chat.id, "🎨 Генерирую изображение...")
    try:
        response = g4f.ChatCompletion.create(model="dall-e-3", messages=[{"role":"user","content":prompt}])
        bot.send_message(m.chat.id, f"Результат: {response}")
    except Exception as e:
        bot.reply_to(m, f"Ошибка генерации: {e}")

@bot.message_handler(commands=['tournament'])
def tournament_reg(m):
    uid = m.from_user.id
    bot.reply_to(m, "Вы зарегистрированы на турнир (тест)")

@bot.message_handler(commands=['auction'])
def auction_cmd(m):
    bot.reply_to(m, "Аукцион временно в разработке")

@bot.message_handler(commands=['guild'])
def guild_cmd(m):
    bot.reply_to(m, "Гильдии временно в разработке")

@bot.message_handler(commands=['case_open'])
def case_open(m):
    uid = m.from_user.id
    u = get_u(uid)
    if not u or u['bal'] < 5000:
        return bot.reply_to(m, "Недостаточно монет")
    db_query("UPDATE users SET balance = balance - 5000 WHERE id=?", (uid,))
    items = ["boost1"]
    prize = random.choice(items)
    db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, prize))
    bot.reply_to(m, f"🎁 Вы открыли кейс и получили {prize}!")

# ==========================================
# 7. ФОНОВЫЙ ВОРКЕР ТУРНИРОВ
# ==========================================
def tournament_worker():
    while True:
        # Здесь будет логика завершения турниров
        time.sleep(3600)

# ==========================================
# 8. ЗАПУСК (RENDER)
# ==========================================
app = Flask(__name__)
@app.route('/')
def home():
    return "S.P.I.R.A. Online", 200

if __name__ == "__main__":
    # Запускаем фоновый воркер для турниров
    threading.Thread(target=tournament_worker, daemon=True).start()
    
    # Запускаем бота в отдельном потоке (не демон, чтобы он не завершился)
    threading.Thread(target=lambda: bot.infinity_polling(timeout=60, skip_pending=True), daemon=False).start()
    
    # Flask в основном потоке
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)