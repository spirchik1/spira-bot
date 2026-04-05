import os, threading, sqlite3, random, time, json, io, requests
from datetime import datetime, timedelta
import telebot
from telebot import types
from flask import Flask
from gtts import gTTS
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
ADMIN_ID = 8632196470  # Замените на свой ID, если нужно (узнайте у @userinfobot)
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

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

# Таблицы
db_query("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT,
    ref_id INTEGER, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
    daily_last TEXT, daily_streak INTEGER DEFAULT 0, lang TEXT DEFAULT 'ru'
)""")
db_query("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0,
    game_dice_wins INTEGER DEFAULT 0, game_coin_wins INTEGER DEFAULT 0, game_slots_wins INTEGER DEFAULT 0,
    game_casino_wins INTEGER DEFAULT 0, game_poker_wins INTEGER DEFAULT 0, game_blackjack_wins INTEGER DEFAULT 0,
    game_wheel_wins INTEGER DEFAULT 0, game_scratch_wins INTEGER DEFAULT 0, max_win INTEGER DEFAULT 0, best_streak INTEGER DEFAULT 0
)""")
db_query("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1, PRIMARY KEY (user_id, item_id))")
db_query("CREATE TABLE IF NOT EXISTS shop_items (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, type TEXT, effect TEXT)")
db_query("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, items TEXT)")
db_query("""CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item_id TEXT, min_bid INTEGER,
    current_bid INTEGER, current_bidder INTEGER, end_time TEXT, status TEXT DEFAULT 'active'
)""")
db_query("""CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, leader_id INTEGER, balance INTEGER DEFAULT 0, level INTEGER DEFAULT 1, created TEXT
)""")
db_query("""CREATE TABLE IF NOT EXISTS guild_members (user_id INTEGER, guild_id INTEGER, role TEXT DEFAULT 'member', PRIMARY KEY (user_id, guild_id))""")
db_query("""CREATE TABLE IF NOT EXISTS quests (
    id INTEGER PRIMARY KEY, name_ru TEXT, goal_type TEXT, goal_count INTEGER, reward_coins INTEGER, reward_exp INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS user_quests (user_id INTEGER, quest_id INTEGER, progress INTEGER DEFAULT 0, completed INTEGER DEFAULT 0, PRIMARY KEY (user_id, quest_id))""")
db_query("""CREATE TABLE IF NOT EXISTS tournaments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, prize_pool INTEGER, participants TEXT, winner_id INTEGER, status TEXT
)""")
db_query("CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)")

# Заполнение начальными данными
db_query("INSERT OR IGNORE INTO shop_items VALUES ('boost1','Буст +20%',5000,'boost','win_chance+20')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"boost1\",\"prob\":1}]')")
for q in [(1,'Сыграй 5 игр','play_games',5,1000,50), (2,'Выиграй 3 игры','win_games',3,2000,100)]:
    db_query("INSERT OR IGNORE INTO quests VALUES (?,?,?,?,?,?)", q)
db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024',10000,50,0)")

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
    # Обновление статистики
    stats, _ = db_query("SELECT * FROM stats WHERE user_id=?", (uid,), True)
    if not stats:
        db_query("INSERT INTO stats (user_id) VALUES (?)", (uid,))
        stats = [(0,0,0,0,0,0,0,0,0,0,0,0)]
    total_games = stats[0][1]+1
    total_wins = stats[0][2]+(1 if win else 0)
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, game_{game}_wins = game_{game}_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    # Обновление квестов
    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))
    # Проверка завершённых квестов
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

# ==========================================
# 4. ИГРЫ (ЧЕРЕЗ КНОПКИ И КОМАНДЫ)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games_menu(m):
    text = "🎲 Выберите игру и сумму ставки:\n\n"
    games = ["dice", "coin", "slots", "casino", "poker", "blackjack", "wheel", "scratch"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for g in games:
        markup.add(types.InlineKeyboardButton(g.capitalize(), callback_data=f"game_{g}"))
    bot.send_message(m.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("game_"))
def game_callback(c):
    game = c.data.split("_")[1]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bet in [100, 500, 1000, 5000]:
        markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"bet_{game}_{bet}"))
    bot.edit_message_text(f"Ставка для игры {game}:", c.message.chat.id, c.message.message_id, reply_markup=markup)

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
    # Списываем
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

# ==========================================
# 5. НЕЙРОСЕТЬ (S.P.I.R.A.)
# ==========================================
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
        sys_prompt = "Ты S.P.I.R.A., создана Spirchik. Отвечай по-русски, кратко. О создателе только если спросят."
        resp = g4f.ChatCompletion.create(model=g4f.models.gpt_35_turbo, messages=[
            {"role":"system","content":sys_prompt},
            {"role":"user","content":msg.text}
        ])
        bot.send_message(msg.chat.id, resp if resp else "Нет ответа")
    except Exception as e:
        bot.send_message(msg.chat.id, f"⚠️ Ошибка ИИ: {e}")

# ==========================================
# 6. ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ (БЕСПЛАТНО, БЕЗ ОШИБОК)
# ==========================================
@bot.message_handler(func=lambda m: m.text == "🎨 Imagine")
def imagine_prompt(m):
    msg = bot.send_message(m.chat.id, "Опишите картинку:")
    bot.register_next_step_handler(msg, generate_image)

@bot.message_handler(commands=['imagine'])
def imagine_cmd(m):
    prompt = m.text.replace("/imagine ", "")
    if not prompt:
        bot.reply_to(m, "Напишите описание после /imagine")
        return
    generate_image_text(m.chat.id, prompt, m.from_user.id)

def generate_image(msg):
    if msg.text:
        generate_image_text(msg.chat.id, msg.text, msg.from_user.id)

def generate_image_text(chat_id, prompt, user_id):
    bot.send_message(chat_id, "🎨 Генерирую изображение...")
    try:
        # Используем бесплатный API pollinations.ai (не требует ключей)
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            bot.send_photo(chat_id, response.content, caption=f"Ваш запрос: {prompt}")
        else:
            bot.send_message(chat_id, "Не удалось сгенерировать картинку")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {e}")

# ==========================================
# 7. ОСТАЛЬНЫЕ ФУНКЦИИ (КОМАНДЫ И КНОПКИ)
# ==========================================
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
    bot.send_message(m.chat.id, "🦾 S.P.I.R.A. v27.0", reply_markup=main_kb())

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
        bot.send_message(m.chat.id, f"🔗 Ваша реферальная ссылка:\n{link}\nЗа каждого друга +5000 🪙")
    else:
        bot.send_message(m.chat.id, "У бота нет username")

@bot.message_handler(commands=['ref'])
def ref_cmd(m):
    ref_btn(m)

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
    items = ["boost1"]
    prize = random.choice(items)
    db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, prize))
    bot.reply_to(m, f"🎁 Вы открыли кейс и получили {prize}!")

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
        text = "📦 Ваш инвентарь:\n" + "\n".join([f"{i} x{q}" for i,q in inv])
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
    last, streak = res[0]
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
    stats, _ = db_query("SELECT total_games, total_wins, game_dice_wins, game_coin_wins, game_slots_wins, game_casino_wins, game_poker_wins, game_blackjack_wins, game_wheel_wins, game_scratch_wins FROM stats WHERE user_id=?", (uid,), True)
    if stats:
        s = stats[0]
        text = f"📊 Статистика:\nВсего игр: {s[0]}\nПобед: {s[1]}\n\n🎲 dice: {s[2]}\n🪙 coin: {s[3]}\n🎰 slots: {s[4]}\n🎰 casino: {s[5]}\n🃏 poker: {s[6]}\n🃏 blackjack: {s[7]}\n🎡 wheel: {s[8]}\n🎫 scratch: {s[9]}"
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Нет статистики")

@bot.message_handler(func=lambda m: m.text == "🎤 TTS")
def tts_btn(m):
    msg = bot.send_message(m.chat.id, "Напишите текст для озвучки:")
    bot.register_next_step_handler(msg, tts_generate)

def tts_generate(m):
    text = m.text
    if not text: return
    try:
        tts = gTTS(text, lang='ru')
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        bot.send_voice(m.chat.id, audio)
    except Exception as e:
        bot.reply_to(m, f"Ошибка: {e}")

@bot.message_handler(func=l