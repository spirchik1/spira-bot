import os
import threading
import sqlite3
import random
import time
import json
import re
import io
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import telebot
from telebot import types
from flask import Flask, request
from gtts import gTTS
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
ADMIN_USERNAME = "Spirchik1"  # Твой юзернейм (без @)
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

# Получим ID админа при запуске (автоматически)
ADMIN_ID = None

def get_admin_id():
    global ADMIN_ID
    if ADMIN_ID is not None:
        return ADMIN_ID
    try:
        # Поиск пользователя по username
        user = bot.get_chat(f"@{ADMIN_USERNAME}")
        ADMIN_ID = user.id
        print(f"✅ Администратор определён: {ADMIN_USERNAME} (ID: {ADMIN_ID})")
        return ADMIN_ID
    except Exception as e:
        print(f"⚠️ Не удалось определить админа: {e}. Установите ADMIN_ID вручную.")
        return None

# ==========================================
# 2. БАЗА ДАННЫХ (все таблицы из списка)
# ==========================================
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('spira_mega.db', timeout=30)
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

# ---- Таблицы ----
db_query("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    balance INTEGER,
    mode TEXT,
    prefix TEXT,
    ref_id INTEGER,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    daily_last TEXT,
    daily_streak INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'ru'
)""")

db_query("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY,
    total_games INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    game_dice_wins INTEGER DEFAULT 0,
    game_coin_wins INTEGER DEFAULT 0,
    game_slots_wins INTEGER DEFAULT 0,
    game_casino_wins INTEGER DEFAULT 0,
    game_poker_wins INTEGER DEFAULT 0,
    game_blackjack_wins INTEGER DEFAULT 0,
    game_wheel_wins INTEGER DEFAULT 0,
    game_scratch_wins INTEGER DEFAULT 0,
    max_win INTEGER DEFAULT 0,
    best_streak INTEGER DEFAULT 0
)""")

db_query("""CREATE TABLE IF NOT EXISTS mmr (
    user_id INTEGER,
    game TEXT,
    mmr INTEGER DEFAULT 1000,
    PRIMARY KEY (user_id, game)
)""")

db_query("""CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item_id TEXT,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, item_id)
)""")

db_query("""CREATE TABLE IF NOT EXISTS shop_items (
    id TEXT PRIMARY KEY,
    name_ru TEXT,
    name_en TEXT,
    price INTEGER,
    type TEXT,
    effect TEXT,
    duration INTEGER
)""")

try:
    db_query("INSERT OR IGNORE INTO shop_items VALUES ('boost1', 'Буст на победу +20%', 'Win Boost +20%', 5000, 'boost', 'win_chance+20', 3600)")
    db_query("INSERT OR IGNORE INTO shop_items VALUES ('skin_gold', 'Золотой кубик', 'Golden Dice', 10000, 'skin', 'dice_emoji=🎲✨', 0)")
    db_query("INSERT OR IGNORE INTO shop_items VALUES ('role_legend', 'Легенда 🏆', 'Legend', 50000, 'role', 'prefix=Легенда 🏆', 0)")
except: pass

db_query("""CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    name_ru TEXT,
    price INTEGER,
    items TEXT
)""")
try:
    db_query("INSERT OR IGNORE INTO cases VALUES ('case1', 'Обычный кейс', 5000, '[{\"item\":\"boost1\",\"prob\":0.7},{\"item\":\"skin_gold\",\"prob\":0.3}]')")
except: pass

db_query("""CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER,
    item_id TEXT,
    min_bid INTEGER,
    current_bid INTEGER,
    current_bidder INTEGER,
    end_time TEXT,
    status TEXT DEFAULT 'active'
)""")

db_query("""CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    leader_id INTEGER,
    balance INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    created TEXT
)""")
db_query("""CREATE TABLE IF NOT EXISTS guild_members (
    user_id INTEGER,
    guild_id INTEGER,
    role TEXT DEFAULT 'member',
    PRIMARY KEY (user_id, guild_id)
)""")

db_query("""CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    guild_id INTEGER,
    message TEXT,
    timestamp TEXT
)""")

db_query("""CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ru TEXT,
    name_en TEXT,
    description_ru TEXT,
    description_en TEXT,
    goal_type TEXT,
    goal_count INTEGER,
    reward_coins INTEGER,
    reward_exp INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS user_quests (
    user_id INTEGER,
    quest_id INTEGER,
    progress INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, quest_id)
)""")
try:
    db_query("INSERT OR IGNORE INTO quests VALUES (1, 'Новичок', 'Novice', 'Сыграйте 5 игр', 'Play 5 games', 'play_games', 5, 1000, 50)")
    db_query("INSERT OR IGNORE INTO quests VALUES (2, 'Победитель', 'Winner', 'Выиграйте 3 игры', 'Win 3 games', 'win_games', 3, 2000, 100)")
except: pass

db_query("""CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ru TEXT,
    name_en TEXT,
    condition_type TEXT,
    condition_value INTEGER,
    reward_coins INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INTEGER,
    ach_id INTEGER,
    earned TEXT,
    PRIMARY KEY (user_id, ach_id)
)""")
try:
    db_query("INSERT OR IGNORE INTO achievements VALUES (1, '100 игр', '100 games', 'total_games', 100, 10000)")
    db_query("INSERT OR IGNORE INTO achievements VALUES (2, '10 побед подряд', '10 wins streak', 'streak', 10, 5000)")
except: pass

db_query("""CREATE TABLE IF NOT EXISTS promo (
    code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)""")
try:
    db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024', 10000, 50, 0)")
except: pass

db_query("""CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT,
    end_time TEXT,
    prize_pool INTEGER,
    participants TEXT,
    winner_id INTEGER,
    status TEXT
)""")

# ==========================================
# 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def get_u(uid):
    res, _ = db_query("SELECT balance, mode, prefix, level, exp, lang FROM users WHERE id=?", (uid,), True)
    if res:
        return {
            "bal": res[0][0],
            "mode": res[0][1],
            "prefix": res[0][2],
            "level": res[0][3],
            "exp": res[0][4],
            "lang": res[0][5] or "ru"
        }
    return None

def update_stats(uid, game, win, bet=0):
    exp_gain = bet // 100 + 1 if win else 1
    db_query("UPDATE users SET exp = exp + ? WHERE id=?", (exp_gain, uid))
    u = get_u(uid)
    if u and u['exp'] >= u['level'] * 100:
        new_level = u['level'] + 1
        db_query("UPDATE users SET level = ?, exp = 0 WHERE id=?", (new_level, uid))
        try: bot.send_message(uid, f"🎉 Поздравляем! Вы достигли {new_level} уровня!")
        except: pass

    # Обновляем статистику
    stats, _ = db_query("SELECT * FROM stats WHERE user_id=?", (uid,), True)
    if not stats:
        db_query("INSERT INTO stats (user_id) VALUES (?)", (uid,))
        stats = [(0,0,0,0,0,0,0,0,0,0,0,0)]
    total_games = (stats[0][1] or 0) + 1
    total_wins = (stats[0][2] or 0) + (1 if win else 0)
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, game_{game}_wins = game_{game}_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))

def main_kb(lang="ru"):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🤖 Нейросеть", "🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    markup.add("⚙️ Ежедневный бонус", "🎲 Статистика", "🏅 Достижения")
    return markup

def check_sub(m):
    try:
        status = bot.get_chat_member("@spiraofficial", m.from_user.id).status
        if status in ['member', 'administrator', 'creator']: return True
    except: pass
    bot.send_message(m.chat.id, "⚠️ Подпишитесь на @spiraofficial")
    return False

# ==========================================
# 4. ИГРОВОЙ ДВИЖОК (с авто-возвратом)
# ==========================================
@bot.message_handler(commands=["dice", "coin", "slots", "casino", "poker", "blackjack", "wheel", "scratch"])
def game_handler(m):
    if not check_sub(m): return
    uid = m.from_user.id
    u = get_u(uid)
    if not u: return bot.reply_to(m, "Нажми /start")
    args = m.text.split()
    if len(args) < 2:
        return bot.reply_to(m, "Формат: /игра [ставка]")
    try:
        bet = int(args[1])
        if bet < 10: return bot.reply_to(m, "Минимум 10 🪙")
        if u['bal'] < bet: return bot.reply_to(m, "Недостаточно 🪙")
        game = args[0][1:].split('@')[0].lower()
        # Атомарное списание
        _, affected = db_query("UPDATE users SET balance = balance - ? WHERE id=? AND balance>=?", (bet, uid, bet))
        if affected == 0: return
        win, coeff = False, 2.0
        try:
            if game == "dice":
                dice = bot.send_dice(m.chat.id, "🎲").dice
                if dice.value >= 4: win = True
            elif game == "coin":
                res = random.choice(["Орел", "Решка"])
                bot.send_message(m.chat.id, f"🪙 Выпало: **{res}**", parse_mode="Markdown")
                if res == "Орел": win = True
            elif game in ("slots", "casino"):
                dice = bot.send_dice(m.chat.id, "🎰").dice
                if dice.value in (1,22,43,64): win, coeff = True, 10.0
                elif dice.value in (16,32,48): win, coeff = True, 3.0
            elif game == "poker":
                # упрощённый покер
                player = random.randint(1,13)+random.randint(1,13)
                dealer = random.randint(1,13)+random.randint(1,13)
                win = player > dealer
                coeff = 1.8
            elif game == "blackjack":
                player = random.randint(1,10)+random.randint(1,10)
                dealer = random.randint(1,10)+random.randint(1,10)
                win = player > dealer
                coeff = 1.8
            elif game == "wheel":
                mult = random.choices([0,1,2,5,10], weights=[30,40,20,8,2])[0]
                win = mult > 0
                coeff = mult
            elif game == "scratch":
                symbols = [random.choice(["🍒","🍋","🍊","7"]) for _ in range(3)]
                if symbols[0]==symbols[1]==symbols[2]:
                    win = True
                    coeff = 5 if symbols[0]!="7" else 10
                bot.send_message(m.chat.id, f"🎫 {' '.join(symbols)}")
            if win:
                prize = int(bet * coeff)
                db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
                bot.send_message(m.chat.id, f"🎉 Выигрыш: {prize} 🪙!")
            else:
                bot.send_message(m.chat.id, "💀 Проигрыш.")
            update_stats(uid, game, win, bet)
        except Exception as e:
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, uid))
            bot.send_message(m.chat.id, "⚠️ Ошибка игры, ставка возвращена.")
            print(e)
    except: bot.reply_to(m, "Введите число!")

# ==========================================
# 5. ОСНОВНЫЕ КОМАНДЫ
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid, name = m.from_user.id, m.from_user.first_name
    if not get_u(uid):
        ref = None
        args = m.text.split()
        if len(args)>1 and args[1].isdigit(): ref = args[1]
        db_query("INSERT INTO users VALUES (?, ?, 1000, 'off', 'Новичок 🛡', ?, 1, 0, NULL, 0, 'ru')", (uid, name, ref))
        if ref and int(ref)!=uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try: bot.send_message(ref, "🎁 +5000 🪙 за реферала!")
            except: pass
    if not check_sub(m): return
    bot.send_message(m.chat.id, "🦾 S.P.I.R.A. v25.0", reply_markup=main_kb())

@bot.message_handler(commands=['daily'])
def daily(m):
    uid = m.from_user.id
    u = get_u(uid)
    if not u: return bot.reply_to(m, "/start")
    today = datetime.now().date().isoformat()
    last, streak = db_query("SELECT daily_last, daily_streak FROM users WHERE id=?", (uid,), True)[0]
    if last == today:
        return bot.reply_to(m, "Уже получали сегодня!")
    if last == (datetime.now().date() - timedelta(days=1)).isoformat():
        streak = streak + 1
    else:
        streak = 1
    bonus = 500 + (streak-1)*100
    if bonus>2000: bonus=2000
    db_query("UPDATE users SET balance = balance + ?, daily_last = ?, daily_streak = ? WHERE id=?", (bonus, today, streak, uid))
    bot.reply_to(m, f"✅ +{bonus} 🪙 (Стрик: {streak})")

@bot.message_handler(commands=['balance','bal'])
def balance_cmd(m):
    u = get_u(m.from_user.id)
    bot.reply_to(m, f"💰 Баланс: {u['bal'] if u else 0} 🪙")

@bot.message_handler(commands=['profile'])
def profile_cmd(m):
    u = get_u(m.from_user.id)
    if not u: return
    bot.send_message(m.chat.id, f"👤 {m.from_user.first_name}\nСтатус: {u['prefix']}\nУровень: {u['level']}\nБаланс: {u['bal']} 🪙")

@bot.message_handler(commands=['top'])
def top_cmd(m):
    data, _ = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 5", fetch=True)
    if data:
        text = "🏆 ТОП-5 богачей:\n" + "\n".join([f"{i+1}. {r[0]} – {r[1]} 🪙" for i,r in enumerate(data)])
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Пока никого")

@bot.message_handler(commands=['ref'])
def ref_cmd(m):
    username = bot.get_me().username
    if username:
        link = f"https://t.me/{username}?start={m.from_user.id}"
        bot.send_message(m.chat.id, f"🔗 Ваша ссылка: {link}\n+5000 🪙 за друга")
    else:
        bot.send_message(m.chat.id, "У бота нет username")

@bot.message_handler(commands=['promo'])
def promo_cmd(m):
    msg = bot.send_message(m.chat.id, "Введите промокод:")
    bot.register_next_step_handler(msg, apply_promo)

def apply_promo(m):
    uid, code = m.from_user.id, m.text.upper()
    if db_query("SELECT * FROM used_promos WHERE user_id=? AND code=?", (uid, code), True)[0]:
        return bot.reply_to(m, "Уже использовали")
    promo = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)[0]
    if promo and promo[2] < promo[1]:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (promo[0], uid))
        db_query("UPDATE promo SET used_count = used_count+1 WHERE code=?", (code,))
        db_query("INSERT INTO used_promos VALUES (?,?)", (uid, code))
        bot.reply_to(m, f"✅ +{promo[0]} 🪙")
    else:
        bot.reply_to(m, "Неверный код")

# ==========================================
# 6. ОБРАБОТЧИК ТЕКСТА И ИИ
# ==========================================
@bot.message_handler(content_types=['text'])
def text_logic(m):
    if not check_sub(m): return
    u = get_u(m.from_user.id)
    if not u: return bot.reply_to(m, "/start")
    if m.text == "🛑 Стоп":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        return bot.send_message(m.chat.id, "ИИ выключен", reply_markup=main_kb())
    if u['mode'] == 'ai':
        def ai_work():
            try:
                sys_prompt = "Ты S.P.I.R.A., создана Spirchik. Отвечай по-русски, кратко. О создателе говори только если спросят."
                resp = g4f.ChatCompletion.create(model=g4f.models.gpt_35_turbo, messages=[
                    {"role":"system","content":sys_prompt},
                    {"role":"user","content":m.text}
                ])
                bot.reply_to(m, resp if resp else "Нет ответа")
            except:
                bot.reply_to(m, "⚠️ Ошибка ИИ")
        threading.Thread(target=ai_work).start()
        return
    # Кнопки
    if m.text == "💰 Баланс":
        bot.reply_to(m, f"💰 {u['bal']} 🪙")
    elif m.text == "👤 Профиль":
        profile_cmd(m)
    elif m.text == "🎮 Игры":
        bot.send_message(m.chat.id, "Игры: /dice, /coin, /slots, /casino, /poker, /blackjack, /wheel, /scratch")
    elif m.text == "👥 Рефералы":
        ref_cmd(m)
    elif m.text == "🏆 ТОП":
        top_cmd(m)
    elif m.text == "🎟 Промокод":
        promo_cmd(m)
    elif m.text == "🤖 Нейросеть":
        db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "ИИ включён", reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп"))
    elif m.text == "⚙️ Ежедневный бонус":
        daily(m)
    elif m.text == "📦 Кейсы":
        bot.send_message(m.chat.id, "Кейсы: /case_open case1")
    elif m.text == "🛒 Магазин":
        items, _ = db_query("SELECT name_ru, price, id FROM shop_items", fetch=True)
        text = "🛒 Магазин:\n" + "\n".join([f"{n} – {p} 🪙 (/{b})" for n,p,b in items])
        bot.send_message(m.chat.id, text)
    elif m.text == "🎲 Статистика":
        stats, _ = db_query("SELECT total_games, total_wins FROM stats WHERE user_id=?", (m.from_user.id,), True)
        if stats:
            bot.reply_to(m, f"📊 Игр: {stats[0][0]}, Побед: {stats[0][1]}")
        else:
            bot.reply_to(m, "Нет статистики")
    elif m.text == "🏅 Достижения":
        bot.send_message(m.chat.id, "Достижения в разработке")

# ==========================================
# 7. АДМИН-ПАНЕЛЬ (только для @Spirchik1)
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if m.from_user.id != get_admin_id():
        return bot.reply_to(m, "Нет прав")
    bot.send_message(m.chat.id, "👑 Админ-панель:\n/broadcast [текст]\n/give [id] [сумма]\n/createpromo [код] [награда] [лимит]\n/ban [id]")

@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if m.from_user.id != get_admin_id(): return
    text = m.text.replace("/broadcast ", "")
    if not text: return
    users, _ = db_query("SELECT id FROM users", fetch=True)
    for uid in users:
        try:
            bot.send_message(uid[0], f"📢 Рассылка: {text}")
        except: pass
    bot.reply_to(m, f"Отправлено {len(users)} пользователям")

@bot.message_handler(commands=['give'])
def give_coins(m):
    if m.from_user.id != get_admin_id(): return
    args = m.text.split()
    if len(args) < 3: return
    uid, amount = int(args[1]), int(args[2])
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    bot.reply_to(m, f"✅ {amount} 🪙 выдано {uid}")
    try: bot.send_message(uid, f"🎁 Администратор выдал вам {amount} 🪙")
    except: pass

@bot.message_handler(commands=['createpromo'])
def create_promo(m):
    if m.from_user.id != get_admin_id(): return
    args = m.text.split()
    if len(args) < 4: return
    code, reward, limit = args[1], int(args[2]), int(args[3])
    db_query("INSERT INTO promo VALUES (?, ?, ?, 0)", (code.upper(), reward, limit))
    bot.reply_to(m, f"Промокод {code} создан")

# ==========================================
# 8. FLASK-СЕРВЕР + АВТО-ПИНГ (НЕ ДАЁТ ЗАСНУТЬ)
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. v25.0 is alive", 200

@app.route('/ping')
def ping():
    return "pong", 200

def keep_alive():
    """Каждые 5 минут пингуем самого себя, чтобы Render не усыпил"""
    time.sleep(60)  # дадим боту запуститься
    while True:
        try:
      