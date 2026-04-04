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
ADMIN_USERNAME = "Spirchik1"
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

# Определим админа
ADMIN_ID = None
def get_admin_id():
    global ADMIN_ID
    if ADMIN_ID: return ADMIN_ID
    try:
        ADMIN_ID = bot.get_chat(f"@{ADMIN_USERNAME}").id
        print(f"✅ Админ: {ADMIN_USERNAME} ({ADMIN_ID})")
        return ADMIN_ID
    except:
        print("⚠️ Админ не найден, используйте /setadmin")
        return None

# ==========================================
# 2. БАЗА ДАННЫХ (ВСЕ ТАБЛИЦЫ)
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

# Пользователи
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

# Статистика игр
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

# Рейтинг MMR
db_query("""CREATE TABLE IF NOT EXISTS mmr (
    user_id INTEGER,
    game TEXT,
    mmr INTEGER DEFAULT 1000,
    PRIMARY KEY (user_id, game)
)""")

# Инвентарь
db_query("""CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item_id TEXT,
    quantity INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, item_id)
)""")

# Магазин
db_query("""CREATE TABLE IF NOT EXISTS shop_items (
    id TEXT PRIMARY KEY,
    name_ru TEXT,
    name_en TEXT,
    price INTEGER,
    type TEXT,
    effect TEXT,
    duration INTEGER
)""")
for item in [('boost1','Буст +20%','Win Boost +20%',5000,'boost','win_chance+20',3600),
             ('skin_gold','Золотой кубик','Golden Dice',10000,'skin','dice_emoji=🎲✨',0),
             ('role_legend','Легенда 🏆','Legend',50000,'role','prefix=Легенда 🏆',0)]:
    db_query("INSERT OR IGNORE INTO shop_items VALUES (?,?,?,?,?,?,?)", item)

# Кейсы
db_query("""CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    name_ru TEXT,
    price INTEGER,
    items TEXT
)""")
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"boost1\",\"prob\":0.7},{\"item\":\"skin_gold\",\"prob\":0.3}]')")

# Аукцион
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

# Гильдии
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

# Чат
db_query("""CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    guild_id INTEGER,
    message TEXT,
    timestamp TEXT
)""")

# Задания (квесты)
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
for q in [(1,'Новичок','Novice','Сыграйте 5 игр','Play 5 games','play_games',5,1000,50),
          (2,'Победитель','Winner','Выиграйте 3 игры','Win 3 games','win_games',3,2000,100)]:
    db_query("INSERT OR IGNORE INTO quests VALUES (?,?,?,?,?,?,?,?,?)", q)

# Достижения
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
for a in [(1,'100 игр','100 games','total_games',100,10000),
          (2,'10 побед подряд','10 wins streak','streak',10,5000)]:
    db_query("INSERT OR IGNORE INTO achievements VALUES (?,?,?,?,?,?)", a)

# Промокоды
db_query("""CREATE TABLE IF NOT EXISTS promo (
    code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)""")
db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024', 10000, 50, 0)")

# Турниры
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
        return {"bal":res[0][0],"mode":res[0][1],"prefix":res[0][2],"level":res[0][3],"exp":res[0][4],"lang":res[0][5] or "ru"}
    return None

def update_stats(uid, game, win, bet=0):
    exp_gain = bet//100+1 if win else 1
    db_query("UPDATE users SET exp = exp + ? WHERE id=?", (exp_gain, uid))
    u = get_u(uid)
    if u and u['exp'] >= u['level']*100:
        new_level = u['level']+1
        db_query("UPDATE users SET level = ?, exp = 0 WHERE id=?", (new_level, uid))
        try: bot.send_message(uid, f"🎉 Новый уровень: {new_level}!")
        except: pass
    stats, _ = db_query("SELECT * FROM stats WHERE user_id=?", (uid,), True)
    if not stats:
        db_query("INSERT INTO stats (user_id) VALUES (?)", (uid,))
        stats = [(0,0,0,0,0,0,0,0,0,0,0,0)]
    total_games = (stats[0][1] or 0)+1
    total_wins = (stats[0][2] or 0)+(1 if win else 0)
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, game_{game}_wins = game_{game}_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    # Обновляем задания
    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))
    # Проверка завершения квестов
    qs, _ = db_query("SELECT q.id, q.goal_count, q.reward_coins, q.reward_exp FROM user_quests uq JOIN quests q ON uq.quest_id=q.id WHERE uq.user_id=? AND uq.completed=0 AND uq.progress >= q.goal_count", (uid,), True)
    for qid, goal, coins, exp in qs:
        db_query("UPDATE user_quests SET completed=1 WHERE user_id=? AND quest_id=?", (uid, qid))
        db_query("UPDATE users SET balance = balance + ?, exp = exp + ? WHERE id=?", (coins, exp, uid))
        try: bot.send_message(uid, f"✅ Задание выполнено! +{coins}🪙 +{exp}⭐")
        except: pass

def main_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🤖 Нейросеть", "🎮 Игры", "💰 Баланс", "👤 Профиль")
    m.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    m.add("⚙️ Ежедневный бонус", "🎲 Статистика", "🏅 Достижения", "🎤 TTS", "🎨 Imagine")
    m.add("🏟 Турнир", "⚔️ Аукцион", "📜 Задания", "🏛 Гильдия")
    return m

def check_sub(m):
    try:
        if bot.get_chat_member("@spiraofficial", m.from_user.id).status in ['member','administrator','creator']:
            return True
    except: pass
    bot.send_message(m.chat.id, "⚠️ Подпишитесь на @spiraofficial")
    return False

# ==========================================
# 4. ИГРЫ (ВСЕ)
# ==========================================
@bot.message_handler(commands=["dice","coin","slots","casino","poker","blackjack","wheel","scratch"])
def game_handler(m):
    if not check_sub(m): return
    uid = m.from_user.id
    u = get_u(uid)
    if not u: return bot.reply_to(m, "/start")
    args = m.text.split()
    if len(args)<2: return bot.reply_to(m, "Формат: /игра [ставка]")
    try:
        bet = int(args[1])
        if bet<10: return bot.reply_to(m, "Минимум 10 🪙")
        if u['bal']<bet: return bot.reply_to(m, "Недостаточно 🪙")
        game = args[0][1:].split('@')[0].lower()
        _, affected = db_query("UPDATE users SET balance = balance - ? WHERE id=? AND balance>=?", (bet, uid, bet))
        if affected==0: return
        win, coeff = False, 2.0
        try:
            if game=="dice":
                val = bot.send_dice(m.chat.id, "🎲").dice.value
                if val>=4: win=True
            elif game=="coin":
                res = random.choice(["Орел","Решка"])
                bot.send_message(m.chat.id, f"🪙 {res}", parse_mode="Markdown")
                if res=="Орел": win=True
            elif game in ("slots","casino"):
                val = bot.send_dice(m.chat.id, "🎰").dice.value
                if val in (1,22,43,64): win, coeff = True, 10.0
                elif val in (16,32,48): win, coeff = True, 3.0
            elif game=="poker":
                player = random.randint(1,13)+random.randint(1,13)
                dealer = random.randint(1,13)+random.randint(1,13)
                win = player>dealer
                coeff = 1.8
            elif game=="blackjack":
                player = random.randint(1,10)+random.randint(1,10)
                dealer = random.randint(1,10)+random.randint(1,10)
                win = player>dealer
                coeff = 1.8
            elif game=="wheel":
                mult = random.choices([0,1,2,5,10], weights=[30,40,20,8,2])[0]
                win = mult>0
                coeff = mult
            elif game=="scratch":
                sym = [random.choice(["🍒","🍋","🍊","7"]) for _ in range(3)]
                bot.send_message(m.chat.id, f"🎫 {' '.join(sym)}")
                if sym[0]==sym[1]==sym[2]:
                    win = True
                    coeff = 5 if sym[0]!="7" else 10
            if win:
                prize = int(bet*coeff)
                db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
                bot.send_message(m.chat.id, f"🎉 Выигрыш: {prize} 🪙!")
            else:
                bot.send_message(m.chat.id, "💀 Проигрыш.")
            update_stats(uid, game, win, bet)
        except Exception as e:
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, uid))
            bot.send_message(m.chat.id, "⚠️ Ошибка, ставка возвращена")
            print(e)
    except: bot.reply_to(m, "Введите число!")

# ==========================================
# 5. НОВЫЕ ФУНКЦИИ: TTS, IMAGINE, ТУРНИРЫ, АУКЦИОН, ЗАДАНИЯ, ГИЛЬДИИ
# ==========================================
@bot.message_handler(commands=['tts'])
def tts_cmd(m):
    if not check_sub(m): return
    text = m.text.replace("/tts ", "")
    if not text:
        bot.reply_to(m, "Напишите текст после /tts")
        return
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
    if not check_sub(m): return
    prompt = m.text.replace("/imagine ", "")
    if not prompt:
        bot.reply_to(m, "Опишите картинку после /imagine")
        return
    bot.send_message(m.chat.id, "🎨 Генерирую изображение, подождите...")
    try:
        # Используем g4f для генерации изображения (модель DALL-E)
        response = g4f.ChatCompletion.create(
            model="dall-e-3",
            messages=[{"role":"user","content":f"Generate an image: {prompt}"}]
        )
        # g4f возвращает URL картинки в ответе
        if response and "url" in response:
            bot.send_photo(m.chat.id, response['url'])
        else:
            bot.reply_to(m, "Не удалось сгенерировать картинку")
    except Exception as e:
        bot.reply_to(m, f"Ошибка: {e}")

# Турниры
@bot.message_handler(commands=['tournament'])
def tournament_cmd(m):
    if not check_sub(m): return
    uid = m.from_user.id
    # Проверка, есть ли активный турнир
    now = datetime.now().isoformat()
    tour, _ = db_query("SELECT id, prize_pool, participants FROM tournaments WHERE status='active' AND end_time > ?", (now,), True)
    if not tour:
        bot.reply_to(m, "Нет активного турнира. Ожидайте следующий (каждые 6 часов)")
        return
    tid, prize, parts_json = tour[0]
    participants = json.loads(parts_json) if parts_json else []
    if uid in participants:
        bot.reply_to(m, "Вы уже участвуете")
        return
    participants.append(uid)
    db_query("UPDATE tournaments SET participants = ? WHERE id=?", (json.dumps(participants), tid))
    bot.reply_to(m, f"Вы записаны на турнир! Призовой фонд: {prize} 🪙")

# Фоновая задача для турниров (запускаем в потоке)
def tournament_worker():
    while True:
        time.sleep(60)
        now = datetime.now()
        # Проверяем, нужно ли создать новый турнир (каждые 6 часов)
        last_tour, _ = db_query("SELECT start_time FROM tournaments ORDER BY id DESC LIMIT 1", fetch=True)
        if not last_tour or (datetime.now() - datetime.fromisoformat(last_tour[0][0])).total_seconds() > 21600:
            start = now
            end = now + timedelta(hours=1)
            prize = 10000
            db_query("INSERT INTO tournaments (start_time, end_time, prize_pool, participants, status) VALUES (?, ?, ?, ?, 'active')",
                     (start.isoformat(), end.isoformat(), prize, json.dumps([])))
        # Проверяем завершённые турниры
        finished, _ = db_query("SELECT id, prize_pool, participants FROM tournaments WHERE status='active' AND end_time < ?", (now.isoformat(),), True)
        for tid, prize, parts_json in finished:
            participants = json.loads(parts_json) if parts_json else []
            if participants:
                winner = random.choice(participants)
                db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, winner))
                try: bot.send_message(winner, f"🏆 Вы выиграли турнир! +{prize} 🪙")
                except: pass
            db_query("UPDATE tournaments SET status='finished', winner_id=? WHERE id=?", (winner if participants else None, tid))

# Аукцион
@bot.message_handler(commands=['auction'])
def auction_cmd(m):
    if not check_sub(m): return
    args = m.text.split()
    if len(args) < 2:
        bot.reply_to(m, "Доступные действия:\n/auction list\n/auction sell [item_id] [min_bid]\n/auction bid [lot_id] [sum]")
        return
    action = args[1].lower()
    uid = m.from_user.id
    if action == "list":
        lots, _ = db_query("SELECT id, seller_id, item_id, min_bid, current_bid, end_time FROM auctions WHERE status='active'", fetch=True)
        if not lots:
            bot.reply_to(m, "Нет активных лотов")
            return
        text = "🏷 Активные лоты:\n"
        for lot in lots:
            text += f"ID {lot[0]}: {lot[2]} | Ставка: {lot[4] or lot[3]} | До {lot[5][:16]}\n"
        bot.send_message(m.chat.id, text)
    elif action == "sell":
        if len(args)<4: return
        item_id = args[2]
        min_bid = int(args[3])
        # Проверяем наличие предмета в инвентаре
        inv, _ = db_query("SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id), True)
        if not inv or inv[0][0] < 1:
            bot.reply_to(m, "У вас нет такого предмета")
            return
        db_query("INSERT INTO auctions (seller_id, item_id, min_bid, current_bid, end_time) VALUES (?,?,?,?,?)",
                 (uid, item_id, min_bid, min_bid, (datetime.now()+timedelta(hours=24)).isoformat()))
        bot.reply_to(m, f"Лот {item_id} выставлен на 24 часа")
    elif action == "bid":
        if len(args)<4: return
        lot_id = int(args[2])
        bid = int(args[3])
        lot, _ = db_query("SELECT seller_id, current_bid, min_bid FROM auctions WHERE id=? AND status='active'", (lot_id,), True)
        if not lot:
            bot.reply_to(m, "Лот не найден")
            return
        seller, curr, minb = lot[0]
        if uid == seller:
            bot.reply_to(m, "Нельзя торговаться за свой лот")
            return
        if bid <= curr:
            bot.reply_to(m, f"Ставка должна быть больше {curr}")
            return
        u = get_u(uid)
        if u['bal'] < bid:
            bot.reply_to(m, "Недостаточно монет")
            return
        # Заморозка монет (просто проверка, потом спишем при победе)
        db_query("UPDATE auctions SET current_bid=?, current_bidder=? WHERE id=?", (bid, uid, lot_id))
        bot.reply_to(m, f"Ставка {bid} принята!")

# Задания (список и прогресс)
@bot.message_handler(commands=['quests'])
def quests_list(m):
    if not check_sub(m): return
    uid = m.from_user.id
    quests, _ = db_query("SELECT id, name_ru, description_ru, goal_count FROM quests", fetch=True)
    user_q, _ = db_query("SELECT quest_id, progress, completed FROM user_quests WHERE user_id=?", (uid,), True)
    prog_dict = {pq[0]: (pq[1], pq[2]) for pq in user_q}
    text = "📜 Ваши задания:\n"
    for qid, name, desc, goal in quests:
        prog, done = prog_dict.get(qid, (0,0))
        status = "✅" if done else f"{prog}/{goal}"
        text += f"{status} {name}: {desc}\n"
    bot.send_message(m.chat.id, text)

# Гильдии
@bot.message_handler(commands=['guild'])
def guild_cmd(m):
    if not check_sub(m): return
    args = m.text.split()
    if len(args) < 2:
        bot.reply_to(m, "/guild create [название]\n/guild join [id]\n/guild info\n/guild leave")
        return
    action = args[1].lower()
    uid = m.from_user.id
    if action == "create":
        if len(args)<3: return
        name = " ".join(args[2:])
        db_query("INSERT INTO guilds (name, leader_id, created) VALUES (?, ?, ?)", (name, uid, datetime.now().isoformat()))
        gid = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
        db_query("INSERT INTO guild_members VALUES (?, ?, 'leader')", (uid, gid))
        bot.reply_to(m, f"Гильдия {name} создана!")
    elif action == "join":
        if len(args)<3: return
        gid = int(args[2])
        # Проверка, есть ли уже участник
        mem, _ = db_query("SELECT user_id FROM guild_members WHERE user_id=? AND guild_id=?", (uid, gid), True)
        if mem:
            bot.reply_to(m, "Вы уже в гильдии")
            return