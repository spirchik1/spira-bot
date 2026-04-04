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

# Создание всех таблиц (пользователи, статы, инвентарь и т.д.)
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
        elif game == "slots":
            val = bot.send_dice(m.chat.id, "🎰").dice.value
            if val in (1, 22, 43, 64): win, coeff = True, 10.0
        
        if win:
            prize = int(bet * coeff)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
            bot.send_message(m.chat.id, f"✅ Выигрыш: {prize} 🪙")
        else:
            bot.send_message(m.chat.id, "❌ Проигрыш")
    except: bot.reply_to(m, "Введите число!")

# ==========================================
# 5. ДОП. ФУНКЦИИ (TTS, Imagine, Guilds)
# ==========================================
@bot.message_handler(commands=['tts'])
def tts_cmd(m):
    text = m.text.replace("/tts ", "")
    if not text: return bot.reply_to(m, "Введите текст")
    tts = gTTS(text, lang='ru')
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    audio.seek(0)
    bot.send_voice(m.chat.id, audio)

@bot.message_handler(commands=['imagine'])
def imagine_cmd(m):
    prompt = m.text.replace("/imagine ", "")
    if not prompt: return bot.reply_to(m, "Опишите картинку")
    bot.send_message(m.chat.id, "🎨 Рисую...")
    try:
        response = g4f.ChatCompletion.create(model="dall-e-3", messages=[{"role":"user","content":prompt}])
        bot.send_message(m.chat.id, f"Результат: {response}")
    except: bot.reply_to(m, "Ошибка генерации")

# Фоновый воркер для турниров
def tournament_worker():
    while True:
        # Тут логика завершения турниров раз в час
        time.sleep(3600)

# ==========================================
# 6. ЗАПУСК (RENDER)
# ==========================================
app = Flask(__name__)
@app.route('/')
def home(): return "S.P.I.R.A. Online", 200

if __name__ == "__main__":
    # Турниры в фоне
    threading.Thread(target=tournament_worker, daemon=True).start()
    
    # Бот в фоне
    print("🤖 Бот запущен...")
    threading.Thread(target=lambda: bot.infinity_polling(timeout=60, skip_pending=True), daemon=True).start()
    
    # Flask в главном потоке для Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
