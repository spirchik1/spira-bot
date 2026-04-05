import os
import threading
import sqlite3
import random
import time
import json
import io
import requests
import logging
from datetime import datetime, timedelta
from flask import Flask
import telebot
from telebot import types
from gtts import gTTS

# Импорт g4f с проверкой
try:
    import g4f
    if hasattr(g4f, 'models'):
        GPT_MODEL = getattr(g4f.models, 'gpt_35_turbo', None)
        if GPT_MODEL is None:
            GPT_MODEL = "gpt-3.5-turbo"
    else:
        GPT_MODEL = "gpt-3.5-turbo"
except ImportError:
    GPT_MODEL = None
    print("g4f not installed")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
ADMIN_ID = 6133141754  # Ваш ID
CHANNEL_ID = "@spiraofficial"

bot = telebot.TeleBot(TOKEN, threaded=True)

# ======================== БАЗА ДАННЫХ ========================
def db_query(query, params=(), fetch=False):
    conn = None
    try:
        conn = sqlite3.connect('spira_full.db', timeout=30, check_same_thread=False)
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            data = cur.fetchall()
        else:
            data = []
        conn.commit()
        return data, cur.rowcount
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()

# Создание таблиц
db_query("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT,
    ref_id INTEGER, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
    daily_last TEXT, daily_streak INTEGER DEFAULT 0, lang TEXT DEFAULT 'ru'
)""")
db_query("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0,
    game_dice_wins INTEGER DEFAULT 0, game_coin_wins INTEGER DEFAULT 0, game_slots_wins INTEGER DEFAULT 0,
    game_casino_wins INTEGER DEFAULT 0, game_poker_wins INTEGER DEFAULT 0, game_blackjack_wins INTEGER DEFAULT 0,
    game_wheel_wins INTEGER DEFAULT 0, game_scratch_wins INTEGER DEFAULT 0
)""")
db_query("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1, PRIMARY KEY (user_id, item_id))")
db_query("CREATE TABLE IF NOT EXISTS shop_items (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, type TEXT, effect TEXT)")
db_query("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, items TEXT)")
db_query("CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item_id TEXT, min_bid INTEGER, current_bid INTEGER, current_bidder INTEGER, end_time TEXT, status TEXT DEFAULT 'active')")
db_query("CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, leader_id INTEGER, balance INTEGER DEFAULT 0, level INTEGER DEFAULT 1, created TEXT)")
db_query("CREATE TABLE IF NOT EXISTS guild_members (user_id INTEGER, guild_id INTEGER, role TEXT DEFAULT 'member', PRIMARY KEY (user_id, guild_id))")
db_query("CREATE TABLE IF NOT EXISTS quests (id INTEGER PRIMARY KEY, name_ru TEXT, goal_type TEXT, goal_count INTEGER, reward_coins INTEGER, reward_exp INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS user_quests (user_id INTEGER, quest_id INTEGER, progress INTEGER DEFAULT 0, completed INTEGER DEFAULT 0, PRIMARY KEY (user_id, quest_id))")
db_query("CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, prize_pool INTEGER, participants TEXT, winner_id INTEGER, status TEXT)")
db_query("CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)")

# Начальные данные
db_query("INSERT OR IGNORE INTO shop_items VALUES ('boost1','Буст +20%',5000,'boost','win_chance+20')")
db_query("INSERT OR IGNORE INTO shop_items VALUES ('skin_gold','Золотой кубик',10000,'skin','dice_emoji=🎲✨')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"boost1\",\"prob\":0.7},{\"item\":\"skin_gold\",\"prob\":0.3}]')")
for q in [(1,'Сыграй 5 игр','play_games',5,1000,50), (2,'Выиграй 3 игры','win_games',3,2000,100)]:
    db_query("INSERT OR IGNORE INTO quests VALUES (?,?,?,?,?,?)", q)
db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024',10000,50,0)")

logger.info("База данных инициализирована")

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
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
        stats = [(0,0,0,0,0,0,0,0,0,0)]
    total_games = (stats[0][1] or 0)+1
    total_wins = (stats[0][2] or 0)+(1 if win else 0)
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, game_{game}_wins = game_{game}_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))
    qs, _ = db_query("SELECT q.id, q.reward_coins, q.reward_exp FROM user_quests uq JOIN quests q ON uq.quest_id=q.id WHERE uq.user_id=? AND uq.completed=0 AND uq.progress >= q.goal_count", (uid,), True)
    for qid, coins, exp in qs:
        db_query("UPDATE user_quests SET completed=1 WHERE user_id=? AND quest_id=?", (uid, qid))
        db_query("UPDATE users SET balance = balance + ?, exp = exp + ? WHERE id=?", (coins, exp, uid))
        try: bot.send_message(uid, f"✅ Задание выполнено! +{coins}🪙 +{exp}⭐")
        except: pass

def check_sub(m):
    try:
        status = bot.get_chat_member(CHANNEL_ID, m.from_user.id).status
        if status in ['member','administrator','creator']: return True
    except: pass
    bot.send_message(m.chat.id, f"⚠️ Подпишитесь на {CHANNEL_ID}")
    return False

def main_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🤖 Нейросеть", "🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    markup.add("⚙️ Бонус", "🎲 Статистика", "🏅 Инвентарь", "🎤 TTS", "🎨 Imagine")
    markup.add("🏟 Турнир", "⚔️ Аукцион", "📜 Задания", "🏛 Гильдия")
    return markup

# ======================== ИГРЫ (INLINE) ========================
@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games_menu(m):
    games = ["dice", "coin", "slots", "casino", "poker", "blackjack", "wheel", "scratch"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for g in games:
        markup.add(types.InlineKeyboardButton(g.capitalize(), callback_data=f"game_{g}"))
    bot.send_message(m.chat.id, "🎲 Выберите игру:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("game_"))
def game_callback(c):
    game = c.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bet in [100, 500, 1000, 5000]:
        markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"bet_{game}_{bet}"))
    bot.edit_message_text(f"Ставка для {game}:", c.message.chat.id, c.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("bet_"))
def bet_callback(c):
    _, game, bet = c.data.split("_")
    bet = int(bet)
    uid = c.from_user.id
    u = get_u(uid)
    if not u:
        bot.answer_callback_query(c.id, "Напишите /start")
        return
    if u['bal'] < bet:
        bot.answer_callback_query(c.id, "Недостаточно монет")
        return
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    win, coeff = False, 2.0
    try:
        if game == "dice":
            val = bot.send_dice(c.message.chat.id, "🎲").dice.value
            if val >= 4: win = True
        elif game == "coin":
            win = random.choice([True, False])
            bot.send_message(c.message.chat.id, "🪙 Орел!" if win else "🪙 Решка!")
        elif game in ("slots","casino"):
            val = bot.send_dice(c.message.chat.id, "🎰").dice.value
            if val in (1,22,43,64): win, coeff = True, 10.0
            elif val in (16,32,48): win, coeff = True, 3.0
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
            bot.send_message(c.message.chat.id, f"🎫 {' '.join(sym)}")
            if sym[0]==sym[1]==sym[2]:
                win = True
                coeff = 5 if sym[0]!="7" else 10
        if win:
            prize = int(bet * coeff)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
            bot.send_message(c.message.chat.id, f"✅ Выигрыш: {prize} 🪙")
        else:
            bot.send_message(c.message.chat.id, "❌ Проигрыш")
        update_stats(uid, game, win, bet)
    except Exception as e:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, uid))
        bot.send_message(c.message.chat.id, f"Ошибка игры: {e}")
    bot.answer_callback_query(c.id)

# ======================== НЕЙРОСЕТЬ (g4f) ========================
@bot.message_handler(func=lambda m: m.text == "🤖 Нейросеть")
def ai_mode_on(m):
    db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп")
    bot.send_message(m.chat.id, "📡 Режим ИИ включён. Задайте вопрос.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🛑 Стоп")
def ai_mode_off(m):
    db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
    bot.send_message(m.chat.id, "Режим ИИ выключен", reply_markup=main_kb())

def ai_worker(msg, uid):
    try:
        if GPT_MODEL is None:
            bot.send_message(msg.chat.id, "⚠️ ИИ не установлен (g4f отсутствует)")
            return
        sys_prompt = "Ты S.P.I.R.A., создана Spirchik. Отвечай по-русски, кратко. О создателе только если спросят."
        response = g4f.ChatCompletion.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": msg.text}
            ]
        )
        bot.send_message(msg.chat.id, response if response else "Нет ответа")
    except Exception as e:
        logger.error(f"AI error: {e}")
        bot.send_message(msg.chat.id, f"⚠️ Ошибка ИИ: {str(e)[:100]}")

# ======================== ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ========================
@bot.message_handler(func=lambda m: m.text == "🎨 Imagine")
def imagine_prompt(m):
    msg = bot.send_message(m.chat.id, "Опишите картинку:")
    bot.register_next_step_handler(msg, generate_image)

def generate_image(msg):
    if not msg.text: return
    bot.send_message(msg.chat.id, "🎨 Генерирую изображение...")
    prompt = msg.text
    for attempt in range(2):
        try:
            url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                bot.send_photo(msg.chat.id, response.content, caption=f"Ваш запрос: {prompt[:100]}")
                return
        except Exception as e:
            logger.warning(f"Image attempt {attempt+1} failed: {e}")
            time.sleep(2)
    bot.send_message(msg.chat.id, "Не удалось сгенерировать картинку. Попробуйте позже.")

# ======================== TTS ========================
@bot.message_handler(func=lambda m: m.text == "🎤 TTS")
def tts_btn(m):
    msg = bot.send_message(m.chat.id, "Напишите текст для озвучки:")
    bot.register_next_step_handler(msg, tts_generate)

def tts_generate(m):
    if not m.text: return
    try:
        tts = gTTS(m.text, lang='ru')
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        bot.send_voice(m.chat.id, audio)
    except Exception as e:
        bot.reply_to(m, f"Ошибка TTS: {e}")

# ======================== ОСНОВНЫЕ КНОПКИ ========================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    u = get_u(uid)
    if not u:
        ref = None
        args = m.text.split()
        if len(args)>1 and args[1].isdigit(): ref = args[1]
        db_query("INSERT INTO users (id, name, balance, ref_id) VALUES (?,?,?,?)", (uid, m.from_user.first_name, 5000, ref))
        if ref and int(ref)!=uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try: bot.send_message(ref, "🎁 +5000 🪙 за реферала!")
            except: pass
        for qid in [1,2]:
            db_query("INSERT OR IGNORE INTO user_quests (user_id, quest_id) VALUES (?,?)", (uid, qid))
    if not check_sub(m): return
    bot.send_message(m.chat.id, "🦾 S.P.I.R.A. v28.0", reply_markup=main_kb())

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance_btn(m):
    u = get_u(m.from_user.id)
    bot.reply_to(m, f"💰 {u['bal'] if u else 0} 🪙")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_btn(m):
    u = get_u(m.from_user.id)
    if u:
        text = f"👤 {m.from_user.first_name}\nУровень: {u['level']}\nОпыт: {u['exp']}/{u['level']*100}\nБаланс: {u['bal']} 🪙\nСтатус: {u['prefix']}"
        bot.reply_to(m, text)

@bot.message_handler(func=lambda m: m.text == "🏆 ТОП")
def top_btn(m):
    data, _ = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 10", fetch=True)
    if data:
        msg = "🏆 ТОП-10 богачей:\n" + "\n".join([f"{i+1}. {row[0]}: {row[1]} 🪙" for i,row in enumerate(data)])
        bot.send_message(m.chat.id, msg)
    else:
        bot.send_message(m.chat.id, "Нет данных")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def ref_btn(m):
    username = bot.get_me().username
    if username:
        link = f"https://t.me/{username}?start={m.from_user.id}"
        bot.send_message(m.chat.id, f"🔗 Ваша ссылка:\n{link}\n+5000 🪙 за друга")
    else:
        bot.send_message(m.chat.id, "У бота нет username")

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_btn(m):
    msg = bot.send_message(m.chat.id, "Введите промокод:")
    bot.register_next_step_handler(msg, apply_promo)

def apply_promo(m):
    uid, code = m.from_user.id, m.text.upper()
    if db_query("SELECT * FROM used_promos WHERE user_id=? AND code=?", (uid, code), True)[0]:
        return bot.reply_to(m, "Уже использовали")
    promo = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)
    if promo and promo[0][2] < promo[0][1]:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (promo[0][0], uid))
        db_query("UPDATE promo SET used_count = used_count+1 WHERE code=?", (code,))
        db_query("INSERT INTO used_promos VALUES (?,?)", (uid, code))
        bot.reply_to(m, f"✅ +{promo[0][0]} 🪙")
    else:
        bot.reply_to(m, "Неверный код")

@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def case_btn(m):
    bot.send_message(m.chat.id, "Кейс 'Обычный кейс' - 5000 🪙\nОткрыть: /case_open case1")

@bot.message_handler(commands=['case_open'])
def case_open(m):
    uid = m.from_user.id
    u = get_u(uid)
    if not u or u['bal'] < 5000:
        return bot.reply_to(m, "Недостаточно монет")
    db_query("UPDATE users SET balance = balance - 5000 WHERE id=?", (uid,))
    case_data, _ = db_query("SELECT items FROM cases WHERE id=?", ("case1",), True)
    items = json.loads(case_data[0][0])
    r = random.random()
    cum = 0
    chosen = None
    for it in items:
        cum += it['prob']
        if r <= cum:
            chosen = it['item']
            break
    if not chosen:
        chosen = items[0]['item']
    db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, chosen))
    bot.reply_to(m, f"🎁 Вы открыли кейс и получили {chosen}!")

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop_btn(m):
    items, _ = db_query("SELECT id, name_ru, price FROM shop_items", fetch=True)
    if items:
        text = "🛒 Магазин:\n" + "\n".join([f"{n} - {p} 🪙 (купить /buy {i})" for i,n,p in items])
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Магазин пуст")

@bot.message_handler(commands=['buy'])
def buy_cmd(m):
    uid = m.from_user.id
    args = m.text.split()
    if len(args)<2: return
    item_id = args[1]
    u = get_u(uid)
    item, _ = db_query("SELECT price FROM shop_items WHERE id=?", (item_id,), True)
    if not item: return bot.reply_to(m, "Товар не найден")
    price = item[0][0]
    if u['bal'] < price: return bot.reply_to(m, "Недостаточно монет")
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (price, uid))
    db_query("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?,?,1) ON CONFLICT(user_id,item_id) DO UPDATE SET quantity = quantity+1", (uid, item_id))
    bot.reply_to(m, f"✅ Вы купили {item_id}")

@bot.message_handler(func=lambda m: m.text == "🏅 Инвентарь")
def inventory_btn(m):
    uid = m.from_user.id
    inv, _ = db_query("SELECT item_id, quantity FROM inventory WHERE user_id=?", (uid,), True)
    if inv:
        text = "📦 Инвентарь:\n" + "\n".join([f"{i} x{q}" for i,q in inv])
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Инвентарь пуст")

@bot.message_handler(func=lambda m: m.text == "⚙️ Бонус")
def daily_bonus(m):
    uid = m.from_user.id
    today = datetime.now().date().isoformat()
    u = get_u(uid)
    if not u: return bot.reply_to(m, "/start")
    res, _ = db_query("SELECT daily_last, daily_streak FROM users WHERE id=?", (uid,), True)
    last, streak = res[0] if res else (None, 0)
    if last == today:
        return bot.reply_to(m, "Уже получали сегодня")
    if last == (datetime.now().date() - timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1
    bonus = min(500 + (streak-1)*100, 2000)
    db_query("UPDATE users SET balance = balance + ?, daily_last = ?, daily_streak = ? WHERE id=?", (bonus, today, streak, uid))
    bot.reply_to(m, f"✅ +{bonus} 🪙 (Стрик: {streak})")

@bot.message_handler(func=lambda m: m.text == "🎲 Статистика")
def stats_btn(m):
    uid = m.from_user.id
    stats, _ = db_query("SELECT total_games, total_wins FROM stats WHERE user_id=?", (uid,), True)
    if stats:
        text = f"📊 Статистика:\nВсего игр: {stats[0][0]}\nПобед: {stats[0][1]}"
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Нет статистики")

# ======================== ТУРНИРЫ ========================
@bot.message_handler(func=lambda m: m.text == "🏟 Турнир")
def tournament_menu(m):
    bot.send_message(m.chat.id, "🏆 Турнир каждые 6 часов. Участие: /tournament_join")

@bot.message_handler(commands=['tournament_join'])
def tournament_join(m):
    uid = m.from_user.id
    now = datetime.now().isoformat()
    tour, _ = db_query("SELECT id, participants FROM tournaments WHERE status='active' AND end_time > ?", (now,), True)
    if not tour:
        start = datetime.now()
        end = start + timedelta(hours=6)
        prize = 10000
        db_query("INSERT INTO tournaments (start_time, end_time, prize_pool, participants, status) VALUES (?,?,?,?,'active')",
                 (start.isoformat(), end.isoformat(), prize, json.dumps([])))
        tour, _ = db_query("SELECT id, participants FROM tournaments WHERE status='active'", fetch=True)
    tid, parts_json = tour[0]
    participants = json.loads(parts_json) if parts_json else []
    if uid in participants:
        return bot.reply_to(m, "Вы уже участвуете")
    participants.append(uid)
    db_query("UPDATE tournaments SET participants = ? WHERE id=?", (json.dumps(participants), tid))
    bot.reply_to(m, "✅ Вы записаны на турнир!")

def tournament_worker():
    while True:
        time.sleep(60)
        now = datetime.now()
        finished, _ = db_query("SELECT id, prize_pool, participants FROM tournaments WHERE status='active' AND end_time < ?", (now.isoformat(),), True)
        for tid, prize, parts_json in finished:
            participants = json.loads(parts_json) if parts_json else []
            if participants:
                winner = random.choice(participants)
                db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, winner))
                try: bot.send_message(winner, f"🏆 Вы выиграли турнир! +{prize} 🪙")
                except: pass
                db_query("UPDATE tournaments SET status='finished', winner_id=? WHERE id=?", (winner, tid))
            else:
                db_query("UPDATE tournaments SET status='finished' WHERE id=?", (tid,))
        active, _ = db_query("SELECT id FROM tournaments WHERE status='active'", fetch=True)
        if not active:
            start = now
            end = start + timedelta(hours=6)
            prize = 10000
            db_query("INSERT INTO tournaments (start_time, end_time, prize_pool, participants, status) VALUES (?,?,?,?,'active')",
                     (start.isoformat(), end.isoformat(), prize, json.dumps([])))

# ======================== АУКЦИОН ========================
@bot.message_handler(func=lambda m: m.text == "⚔️ Аукцион")
def auction_menu(m):
    bot.send_message(m.chat.id, "Аукцион:\n/auction list - список лотов\n/auction sell [item] [min_bid] - выставить\n/auction bid [lot_id] [sum] - сделать ставку")

@bot.message_handler(commands=['auction'])
def auction_cmd(m):
    args = m.text.split()
    if len(args)<2:
        bot.reply_to(m, "Используйте: /auction list|sell|bid")
        return
    action = args[1].lower()
    uid = m.from_user.id
    if action == "list":
        lots, _ = db_query("SELECT id, seller_id, item_id, current_bid, end_time FROM auctions WHERE status='active'", fetch=True)
        if not lots:
            bot.reply_to(m, "Нет активных лотов")
            return
        text = "🏷 Активные лоты:\n"
        for l in lots:
            text += f"ID {l[0]}: {l[2]} | Ставка: {l[3]} | До {l[4][:16]}\n"
        bot.send_message(m.chat.id, text)
    elif action == "sell":
        if len(args)<4: return
        item_id = args[2]
        min_bid = int(args[3])
        inv, _ = db_query("SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id), True)
        if not inv or inv[0][0]<1:
            bot.reply_to(m, "У вас нет такого предмета")
            return
        end = (datetime.now()+timedelta(hours=24)).isoformat()
        db_query("INSERT INTO auctions (seller_id, item_id, min_bid, current_bid, end_time) VALUES (?,?,?,?,?)",
                 (uid, item_id, min_bid, min_bid, end))
        bot.reply_to(m, f"Лот {item_id} выставлен на 24 часа")
    elif action == "bid":
        if len(args)<4: return
        lot_id = int(args[2])
        bid = int(args[3])
        lot, _ = db_query("SELECT seller_id, current_bid FROM auctions WHERE id=? AND status='active'", (lot_id,), True)
        if not lot:
            bot.reply_to(m, "Лот не найден")
            return
        seller, curr = lot[0]
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
        db_query("UPDATE auctions SET current_bid=?, current_bidder=? WHERE id=?", (bid, uid, lot_id))
        bot.reply_to(m, f"Ставка {bid} принята!")

def auction_worker():
    while True:
        time.sleep(60)
        now = datetime.now().isoformat()
        ended, _ = db_query("SELECT id, seller_id, current_bidder, current_bid, item_id FROM auctions WHERE status='active' AND end_time < ?", (now,), True)
        for aid, seller, buyer, price, item in ended:
            if buyer:
                db_query("DELETE FROM inventory WHERE user_id=? AND item_id=?", (seller, item))
                db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (buyer, item))
                db_query("UPDATE users SET balance = balance + ? WHERE id=?", (price, seller))
                db_query("UPDATE users SET balance = balance - ? WHERE id=?", (price, buyer))
                try:
                    bot.send_message(seller, f"💰 Ваш лот {item} продан за {price} 🪙")
                    bot.send_message(buyer, f"🎉 Вы выиграли лот {item} за {price} 🪙")
                except: pass
            db_query("UPDATE auctions SET status='finished' WHERE id=?", (aid,))

# ======================== ЗАДАНИЯ ========================
@bot.message_handler(func=lambda m: m.text == "📜 Задания")
def quests_btn(m):
    uid = m.from_user.id
    quests, _ = db_query("SELECT id, name_ru, goal_count FROM quests", fetch=True)
    user_q, _ = db_query("SELECT quest_id, progress, completed FROM user_quests WHERE user_id=?", (uid,), True)
    prog = {q[0]:(q[1],q[2]) for q in user_q}
    text = "📜 Ваши задания:\n"
    for qid, name, goal in quests:
        p, done = prog.get(qid, (0,0))
        status = "✅" if done else f"{p}/{goal}"
        text += f"{status} {name}\n"
    bot.send_message(m.chat.id, text)

# ======================== ГИЛЬДИИ ========================
@bot.message_handler(func=lambda m: m.text == "🏛 Гильдия")
def guild_menu(m):
    bot.send_message(m.chat.id, "Гильдии:\n/guild create [название]\n/guild join [id]\n/guild info [id]\n/guild leave")

@bot.message_handler(commands=['guild'])
def guild_cmd(m):
    args = m.text.split()
    if len(args)<2:
        bot.reply_to(m, "Используйте: /guild create|join|info|leave")
        return
    action = args[1].lower()
    uid = m.from_user.id
    if action == "create":
        if len(args)<3: return
        name = " ".join(args[2:])
        db_query("INSERT INTO guilds (name, leader_id, created) VALUES (?,?,?)", (name, uid, datetime.now().isoformat()))
        gid = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
        db_query("INSERT INTO guild_members VALUES (?,?,?)", (uid, gid, "leader"))
        bot.reply_to(m, f"Гильдия {name} создана! ID: {gid}")
    elif action == "join":
        if len(args)<3: return
        gid = int(args[2])
        mem, _ = db_query("SELECT user_id FROM guild_members WHERE user_id=? AND guild_id=?", (uid, gid), True)
        if mem:
            bot.reply_to(m, "Вы уже в гильдии")
            return
        db_query("INSERT INTO guild_members VALUES (?,?,?)", (uid, gid, "member"))
        bot.reply_to(m, f"Вы вступили в гильдию {gid}")
    elif action == "info":
        if len(args)<3: return
        gid = int(args[2])
        guild, _ = db_query("SELECT name, leader_id, balance, level FROM guilds WHERE id=?", (gid,), True)
        if not guild: return
        name, lid, bal, lvl = guild[0]
        cnt, _ = db_query("SELECT COUNT(*) FROM guild_members WHERE guild_id=?", (gid,), True)
        bot.send_message(m.chat.id, f"🏛 {name}\nЛидер: {lid}\nУровень: {lvl}\nКазна: {bal}\nУчастников: {cnt[0][0]}")
    elif action == "leave":
        db_query("DELETE FROM guild_members WHERE user_id=? AND guild_id IN (SELECT id FROM guilds WHERE leader_id!=?)", (uid, uid))
        bot.reply_to(m, "Вы покинули гильдию")

# ======================== ОБЩИЙ ОБРАБОТЧИК ТЕКСТА ========================
@bot.message_handler(content_types=['text'])
def text_handler(m):
    if not check_sub(m): return
    uid = m.from_user.id
    u = get_u(uid)
    if not u:
        bot.reply_to(m, "/start")
        return
    if u['mode'] == 'ai':
        threading.Thread(target=ai_worker, args=(m, uid)).start()
        return

# ======================== АДМИН-ПАНЕЛЬ ========================
@bot.message_handler(commands=['admin'])
def admin_panel(m):
    if m.from_user.id != ADMIN_ID: return
    bot.send_message(m.chat.id, "👑 Админ-панель:\n/broadcast [текст]\n/give [id] [сумма]\n/createpromo [код] [награда] [лимит]\n/ban [id]")

@bot.message_handler(commands=['broadcast'])
def broadcast(m):
    if m.from_user.id != ADMIN_ID: return
    text = m.text.replace("/broadcast ", "")
    if not text: return
    users, _ = db_query("SELECT id FROM users", fetch=True)
    for uid in users:
        try: bot.send_message(uid[0], f"📢 {text}")
        except: pass
    bot.reply_to(m, f"Отправлено {len(users)}")

@bot.message_handler(commands=['give'])
def give(m):
    if m.from_user.id != ADMIN_ID: return
    args = m.text.split()
    if len(args)<3: return
    uid, amt = int(args[1]), int(args[2])
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (amt, uid))
    bot.reply_to(m, f"✅ +{amt} {uid}")
    try: bot.send_message(uid, f"🎁 Админ выдал {amt} 🪙")
    except: pass

@bot.message_handler(commands=['createpromo'])
def createpromo(m):
    if m.from_user.id != ADMIN_ID: return
    args = m.text.split()
    if len(args)<4: return
    code, reward, limit = args[1].upper(), int(args[2]), int(args[3])
    db_query("INSERT OR IGNORE INTO promo VALUES (?,?,?,0)", (code, reward, limit))
    bot.reply_to(m, f"Промокод {code} создан")

@bot.message_handler(commands=['ban'])
def ban(m):
    if m.from_user.id != ADMIN_ID: return
    args = m.text.split()
    if len(args)<2: return
    uid = int(args[1])
    db_query("DELETE FROM users WHERE id=?", (uid,))
    bot.reply_to(m, f"Пользователь {uid} забанен")

# ======================== ЗАПУСК ========================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. v28.0 работает", 200

if __name__ == "__main__":
    threading.Thread(target=tournament_worker, daemon=True).start()
    threading.Thread(target=auction_worker, daemon=True).start()
    def run_bot():
        while True:
            try:
                logger.info("Запуск бота...")
                bot.infinity_polling(timeout=60, skip_pending=True)
            except Exception as e:
                logger.error(f"Bot polling error: {e}")
                time.sleep(5)
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
