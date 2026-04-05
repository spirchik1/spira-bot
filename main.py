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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"
ADMIN_ID = 6133141754
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

# Создание таблиц (расширенные)
db_query("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT,
    ref_id INTEGER, level INTEGER DEFAULT 1, exp INTEGER DEFAULT 0,
    daily_last TEXT, daily_streak INTEGER DEFAULT 0, lang TEXT DEFAULT 'ru'
)""")
db_query("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY, total_games INTEGER DEFAULT 0, total_wins INTEGER DEFAULT 0,
    game_dice_wins INTEGER DEFAULT 0, game_coin_wins INTEGER DEFAULT 0, game_slots_wins INTEGER DEFAULT 0,
    game_casino_wins INTEGER DEFAULT 0, game_tic_tac_toe_wins INTEGER DEFAULT 0, game_mines_wins INTEGER DEFAULT 0
)""")
db_query("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item_id TEXT, quantity INTEGER DEFAULT 1, PRIMARY KEY (user_id, item_id))")
db_query("CREATE TABLE IF NOT EXISTS shop_items (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, type TEXT, effect TEXT)")
db_query("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, name_ru TEXT, price INTEGER, items TEXT)")
db_query("CREATE TABLE IF NOT EXISTS auctions (id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER, item_id TEXT, min_bid INTEGER, current_bid INTEGER, current_bidder INTEGER, end_time TEXT, status TEXT DEFAULT 'active')")
db_query("CREATE TABLE IF NOT EXISTS guilds (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, leader_id INTEGER, balance INTEGER DEFAULT 0, level INTEGER DEFAULT 1, created TEXT)")
db_query("CREATE TABLE IF NOT EXISTS guild_members (user_id INTEGER, guild_id INTEGER, role TEXT DEFAULT 'member', PRIMARY KEY (user_id, guild_id))")
db_query("CREATE TABLE IF NOT EXISTS quests (id INTEGER PRIMARY KEY, name_ru TEXT, goal_type TEXT, goal_count INTEGER, reward_coins INTEGER, reward_exp INTEGER, reward_prefix TEXT)")
db_query("CREATE TABLE IF NOT EXISTS user_quests (user_id INTEGER, quest_id INTEGER, progress INTEGER DEFAULT 0, completed INTEGER DEFAULT 0, PRIMARY KEY (user_id, quest_id))")
db_query("CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, start_time TEXT, end_time TEXT, prize_pool INTEGER, participants TEXT, winner_id INTEGER, status TEXT)")
db_query("CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)")
db_query("CREATE TABLE IF NOT EXISTS ttt_games (chat_id INTEGER, player1 INTEGER, player2 INTEGER, board TEXT, turn INTEGER, status TEXT, bet INTEGER, winner_id INTEGER)")

# Заполнение магазина префиксами (20+)
prefixes = [
    ('prefix_newbie', 'Новичок 🛡', 0, 'role'),
    ('prefix_winner', 'Победитель 🏅', 5000, 'role'),
    ('prefix_lucky', 'Везунчик 🍀', 10000, 'role'),
    ('prefix_legend', 'Легенда 🏆', 25000, 'role'),
    ('prefix_king', 'Король 👑', 50000, 'role'),
    ('prefix_master', 'Мастер 🎯', 75000, 'role'),
    ('prefix_god', 'Бог 💎', 100000, 'role'),
    ('prefix_gambler', 'Азартный 🎲', 15000, 'role'),
    ('prefix_rich', 'Богач 💰', 30000, 'role'),
    ('prefix_pro', 'Профи ⚡', 40000, 'role'),
    ('prefix_veteran', 'Ветеран 🎖️', 60000, 'role'),
    ('prefix_diamond', 'Алмазный 💎', 80000, 'role'),
    ('prefix_phoenix', 'Феникс 🔥', 120000, 'role'),
    ('prefix_dragon', 'Дракон 🐉', 150000, 'role'),
    ('prefix_mystic', 'Мистик ✨', 200000, 'role'),
    ('prefix_hero', 'Герой 🦸', 250000, 'role'),
    ('prefix_champion', 'Чемпион 🏅', 300000, 'role'),
    ('prefix_immortal', 'Бессмертный ⚜️', 500000, 'role'),
    ('prefix_creator', 'Создатель 🛠️', 1000000, 'role'),
]
for p in prefixes:
    db_query("INSERT OR IGNORE INTO shop_items VALUES (?,?,?,?,?)", (p[0], p[1], p[2], p[3], ''))

# Добавляем бусты и скины
db_query("INSERT OR IGNORE INTO shop_items VALUES ('boost1','Буст +20%',5000,'boost','win_chance+20')")
db_query("INSERT OR IGNORE INTO shop_items VALUES ('skin_gold','Золотой кубик',10000,'skin','dice_emoji=🎲✨')")

# Кейсы (обычный, редкий, легендарный)
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"prefix_winner\",\"prob\":0.3},{\"item\":\"boost1\",\"prob\":0.7}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case2','Редкий кейс',15000,'[{\"item\":\"prefix_legend\",\"prob\":0.2},{\"item\":\"prefix_king\",\"prob\":0.3},{\"item\":\"skin_gold\",\"prob\":0.5}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case3','Легендарный кейс',50000,'[{\"item\":\"prefix_god\",\"prob\":0.1},{\"item\":\"prefix_dragon\",\"prob\":0.2},{\"item\":\"prefix_immortal\",\"prob\":0.7}]')")

# Задания (расширенные)
quests_data = [
    (1,'Сыграй 5 игр','play_games',5,1000,50,''),
    (2,'Выиграй 3 игры','win_games',3,2000,100,'prefix_winner'),
    (3,'Открой 2 кейса','open_cases',2,3000,150,'prefix_lucky'),
    (4,'Купи 1 префикс','buy_prefix',1,5000,200,'prefix_master'),
    (5,'Пригласи друга','referral',1,10000,300,'prefix_rich'),
    (6,'Выиграй в крестики-нолики','ttt_win',3,4000,150,'prefix_pro'),
    (7,'Сыграй в мины 5 раз','play_mines',5,3000,100,'prefix_gambler'),
]
for q in quests_data:
    db_query("INSERT OR IGNORE INTO quests VALUES (?,?,?,?,?,?,?)", q)

# Промокод
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
        stats = [(0,0,0,0,0,0,0,0)]
    total_games = (stats[0][1] or 0)+1
    total_wins = (stats[0][2] or 0)+(1 if win else 0)
    # Обновляем статистику конкретной игры
    if game == 'dice':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_dice_wins = game_dice_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    elif game == 'coin':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_coin_wins = game_coin_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    elif game == 'slots':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_slots_wins = game_slots_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    elif game == 'casino':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_casino_wins = game_casino_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    elif game == 'ttt':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_tic_tac_toe_wins = game_tic_tac_toe_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    elif game == 'mines':
        db_query("UPDATE stats SET total_games=?, total_wins=?, game_mines_wins = game_mines_wins + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))
    # Квесты
    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))
    # Проверка выполнения квестов
    qs, _ = db_query("SELECT q.id, q.reward_coins, q.reward_exp, q.reward_prefix FROM user_quests uq JOIN quests q ON uq.quest_id=q.id WHERE uq.user_id=? AND uq.completed=0 AND uq.progress >= q.goal_count", (uid,), True)
    for qid, coins, exp, prefix_item in qs:
        db_query("UPDATE user_quests SET completed=1 WHERE user_id=? AND quest_id=?", (uid, qid))
        db_query("UPDATE users SET balance = balance + ?, exp = exp + ? WHERE id=?", (coins, exp, uid))
        if prefix_item:
            db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, prefix_item))
            try: bot.send_message(uid, f"✅ Задание выполнено! +{coins}🪙 +{exp}⭐ + префикс {prefix_item}")
            except: pass
        else:
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
    markup.add("🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    markup.add("⚙️ Бонус", "🎲 Статистика", "🏅 Инвентарь", "🎤 TTS", "🎨 Imagine")
    markup.add("🏟 Турнир", "⚔️ Аукцион", "📜 Задания", "🏛 Гильдия")
    return markup
# ======================== ИГРЫ НА УДАЧУ (inline меню) ========================
@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games_menu(m):
    games = ["dice", "coin", "slots", "casino", "ttt", "mines"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for g in games:
        markup.add(types.InlineKeyboardButton(g.capitalize(), callback_data=f"game_{g}"))
    bot.send_message(m.chat.id, "🎲 Выберите игру:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("game_"))
def game_callback(c):
    game = c.data.split("_")[1]
    if game == "ttt":
        # Для крестиков-ноликов спросим ставку и противника
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bet in [100, 500, 1000, 5000]:
            markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"ttt_bet_{bet}"))
        bot.edit_message_text("Выберите ставку для игры в крестики-нолики:", c.message.chat.id, c.message.message_id, reply_markup=markup)
    elif game == "mines":
        # Спросим количество мин
        markup = types.InlineKeyboardMarkup(row_width=5)
        for mines in range(1, 11):
            markup.add(types.InlineKeyboardButton(str(mines), callback_data=f"mines_mines_{mines}"))
        bot.edit_message_text("Сколько мин будет на поле? (1-10):", c.message.chat.id, c.message.message_id, reply_markup=markup)
    else:
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
        elif game == "slots":
            val = bot.send_dice(c.message.chat.id, "🎰").dice.value
            if val in (1,22,43,64): win, coeff = True, 10.0
            elif val in (16,32,48): win, coeff = True, 3.0
        elif game == "casino":
            val = bot.send_dice(c.message.chat.id, "🎰").dice.value
            if val in (1,22,43,64): win, coeff = True, 10.0
            elif val in (16,32,48): win, coeff = True, 3.0
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

# ---------- Крестики-нолики (TTT) ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_bet_"))
def ttt_bet(c):
    bet = int(c.data.split("_")[2])
    uid = c.from_user.id
    u = get_u(uid)
    if not u or u['bal'] < bet:
        bot.answer_callback_query(c.id, "Недостаточно монет")
        return
    # Запрашиваем противника
    msg = bot.send_message(c.message.chat.id, "Введите Telegram ID или username противника для игры на ставку. Или напишите 'бот' для игры с ботом.")
    bot.register_next_step_handler(msg, lambda m: ttt_opponent(m, bet, uid))

def ttt_opponent(m, bet, uid):
    text = m.text.strip()
    if text.lower() == "бот":
        # Игра с ботом
        start_ttt_game(m.chat.id, uid, None, bet)
    else:
        # Попытка найти противника
        try:
            if text.startswith("@"):
                opponent = bot.get_chat(text).id
            else:
                opponent = int(text)
        except:
            bot.send_message(m.chat.id, "Неверный ID или username.")
            return
        if opponent == uid:
            bot.send_message(m.chat.id, "Нельзя играть с самим собой.")
            return
        u_opp = get_u(opponent)
        if not u_opp:
            bot.send_message(m.chat.id, "Противник не зарегистрирован в боте.")
            return
        if u_opp['bal'] < bet:
            bot.send_message(m.chat.id, "У противника недостаточно монет.")
            return
        # Создаём игру
        start_ttt_game(m.chat.id, uid, opponent, bet)

def start_ttt_game(chat_id, player1, player2, bet):
    # Если игра с ботом, player2 = None
    board = [" "]*9
    turn = 1  # 1 - X, 2 - O (бот или игрок)
    status = "active"
    db_query("INSERT INTO ttt_games (chat_id, player1, player2, board, turn, status, bet) VALUES (?,?,?,?,?,?,?)",
             (chat_id, player1, player2, json.dumps(board), turn, status, bet))
    game_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
    send_ttt_board(chat_id, game_id, player1, player2, board, turn, bet)

def send_ttt_board(chat_id, game_id, p1, p2, board, turn, bet):
    text = f"🎮 Крестики-нолики | Ставка: {bet} 🪙\n"
    if p2:
        text += f"Игрок X: {p1}\nИгрок O: {p2}\n"
    else:
        text += f"Игрок X: {p1}\nИгрок O: Бот\n"
    text += f"Ход: {'X' if turn==1 else 'O'}\n\n"
    # Отображаем поле
    for i in range(0,9,3):
        row = board[i:i+3]
        text += " | ".join([c if c!=" " else str(i+1) for c in row]) + "\n" + ("---------\n" if i<6 else "")
    markup = types.InlineKeyboardMarkup(row_width=3)
    for i in range(9):
        if board[i] == " ":
            markup.add(types.InlineKeyboardButton(str(i+1), callback_data=f"ttt_move_{game_id}_{i}"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ttt_move_"))
def ttt_move(c):
    _, game_id, pos = c.data.split("_")
    game_id = int(game_id)
    pos = int(pos)
    uid = c.from_user.id
    game = db_query("SELECT player1, player2, board, turn, status, bet FROM ttt_games WHERE id=?", (game_id,), True)
    if not game:
        bot.answer_callback_query(c.id, "Игра не найдена")
        return
    p1, p2, board_json, turn, status, bet = game[0]
    if status != "active":
        bot.answer_callback_query(c.id, "Игра уже завершена")
        return
    board = json.loads(board_json)
    # Проверка, чей ход
    if (turn == 1 and uid != p1) or (turn == 2 and p2 and uid != p2):
        bot.answer_callback_query(c.id, "Сейчас не ваш ход")
        return
    if p2 is None and turn == 2:
        # Ход бота
        bot.answer_callback_query(c.id, "Сейчас ходит бот")
        return
    if board[pos] != " ":
        bot.answer_callback_query(c.id, "Клетка занята")
        return
    # Делаем ход
    board[pos] = "X" if turn == 1 else "O"
    # Проверка победы или ничьи
    winner = check_ttt_winner(board)
    if winner:
        # Есть победитель
        winner_id = p1 if winner == "X" else p2
        if winner_id:
            prize = int(bet * 1.8)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, winner_id))
            bot.send_message(c.message.chat.id, f"🏆 Игрок {winner_id} выиграл {prize} 🪙!")
            update_stats(winner_id, "ttt", True, bet)
            if p2 and p2 != winner_id:
                update_stats(p2, "ttt", False, bet)
            else:
                update_stats(p1 if winner_id==p2 else p1, "ttt", False, bet)
        else:
            # победа бота
            prize = int(bet * 1.8)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, p1))
            bot.send_message(c.message.chat.id, f"🤖 Бот выиграл! Вы потеряли {bet} 🪙.")
            update_stats(p1, "ttt", False, bet)
        db_query("UPDATE ttt_games SET status='finished', winner_id=? WHERE id=?", (winner_id, game_id))
        return
    if " " not in board:
        # Ничья
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p1))
        if p2:
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p2))
            bot.send_message(c.message.chat.id, "🤝 Ничья! Ставки возвращены.")
        else:
            bot.send_message(c.message.chat.id, "🤝 Ничья с ботом! Ставка возвращена.")
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    # Меняем ход
    new_turn = 2 if turn == 1 else 1
    db_query("UPDATE ttt_games SET board=?, turn=? WHERE id=?", (json.dumps(board), new_turn, game_id))
    if p2 is None and new_turn == 2:
        # Ход бота
        bot_move(game_id)
    else:
        send_ttt_board(c.message.chat.id, game_id, p1, p2, board, new_turn, bet)

def check_ttt_winner(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a]==board[b]==board[c] and board[a]!=" ":
            return board[a]
    return None

def bot_move(game_id):
    game = db_query("SELECT player1, board, turn, bet FROM ttt_games WHERE id=?", (game_id,), True)
    if not game: return
    p1, board_json, turn, bet = game[0]
    board = json.loads(board_json)
    if turn != 2: return
    # Простой бот: выбирает случайную пустую клетку
    empty = [i for i,cell in enumerate(board) if cell==" "]
    if not empty:
        return
    pos = random.choice(empty)
    board[pos] = "O"
    winner = check_ttt_winner(board)
    if winner:
        # Бот выиграл
        db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, p1))
        bot.send_message(p1, f"🤖 Бот выиграл! Вы потеряли {bet} 🪙.")
        update_stats(p1, "ttt", False, bet)
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    if " " not in board:
        # Ничья
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p1))
        bot.send_message(p1, "🤝 Ничья с ботом! Ставка возвращена.")
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    db_query("UPDATE ttt_games SET board=?, turn=1 WHERE id=?", (json.dumps(board), game_id))
    send_ttt_board(p1, game_id, p1, None, board, 1, bet)

# ---------- Игра "Мины" (Mines) ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_mines_"))
def mines_mines(c):
    mines = int(c.data.split("_")[2])
    uid = c.from_user.id
    # Запрашиваем ставку
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bet in [100, 500, 1000, 5000]:
        markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"mines_bet_{mines}_{bet}"))
    bot.edit_message_text(f"Выберите ставку для игры с {mines} минами:", c.message.chat.id, c.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_bet_"))
def mines_bet(c):
    _, mines, bet = c.data.split("_")
    mines = int(mines)
    bet = int(bet)
    uid = c.from_user.id
    u = get_u(uid)
    if not u or u['bal'] < bet:
        bot.answer_callback_query(c.id, "Недостаточно монет")
        return
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    # Генерируем поле 5x5 (25 клеток) с минами
    total_cells = 25
    bomb_positions = random.sample(range(total_cells), mines)
    # Сохраняем игру
    game_state = {"board": ["?"]*25, "bombs": bomb_positions, "revealed": [], "multiplier": 1.0, "bet": bet, "status": "active"}
    # Сохраняем в БД (временная таблица)
    db_query("CREATE TABLE IF NOT EXISTS mines_games (user_id INTEGER, state TEXT)")
    db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
    db_query("INSERT INTO mines_games VALUES (?,?)", (uid, json.dumps(game_state)))
    # Отправляем поле
    send_mines_board(c.message.chat.id, uid, game_state)

def send_mines_board(chat_id, uid, game_state):
    board = game_state["board"]
    text = f"💣 Игра Мины | Ставка: {game_state['bet']} 🪙 | Множитель: {game_state['multiplier']:.2f}x\n"
    # Рисуем сетку 5x5 с inline кнопками
    markup = types.InlineKeyboardMarkup(row_width=5)
    for i in range(25):
        if board[i] == "?":
            markup.add(types.InlineKeyboardButton("?", callback_data=f"mines_open_{i}"))
        elif board[i] == "💣":
            markup.add(types.InlineKeyboardButton("💣", callback_data="mines_no"))
        elif board[i] == "💰":
            markup.add(types.InlineKeyboardButton("💰", callback_data="mines_no"))
        else:
            markup.add(types.InlineKeyboardButton(" ", callback_data="mines_no"))
    # Добавляем кнопку "Забрать выигрыш"
    markup.add(types.InlineKeyboardButton("💰 Забрать выигрыш", callback_data="mines_cashout"))
    bot.send_message(chat_id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mines_open_"))
def mines_open(c):
    pos = int(c.data.split("_")[2])
    uid = c.from_user.id
    game = db_query("SELECT state FROM mines_games WHERE user_id=?", (uid,), True)
    if not game:
        bot.answer_callback_query(c.id, "Нет активной игры")
        return
    game_state = json.loads(game[0][0])
    if game_state["status"] != "active":
        bot.answer_callback_query(c.id, "Игра завершена")
        return
    if pos in game_state["revealed"]:
        bot.answer_callback_query(c.id, "Клетка уже открыта")
        return
    if pos in game_state["bombs"]:
        # Попали на мину
        game_state["board"][pos] = "💣"
        bot.send_message(c.message.chat.id, f"💥 Вы наступили на мину! Проигрыш {game_state['bet']} 🪙")
        db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
        update_stats(uid, "mines", False, game_state['bet'])
        bot.answer_callback_query(c.id, "Проигрыш")
        return
    # Безопасная клетка
    game_state["board"][pos] = "💰"
    game_state["revealed"].append(pos)
    # Множитель: (общее клеток без мин)/(открытые клетки) ~ 25/(25-mines) за каждую? Простая формула:
    # множитель = 1 + (открыто / (всего_без_мин)) * коэф
    safe_cells = 25 - len(game_state["bombs"])
    multiplier = 1 + (len(game_state["revealed"]) / safe_cells) * 2.0
    game_state["multiplier"] = multiplier
    db_query("UPDATE mines_games SET state=? WHERE user_id=?", (json.dumps(game_state), uid))
    send_mines_board(c.message.chat.id, uid, game_state)
    bot.answer_callback_query(c.id, f"Клетка безопасна! Множитель {multiplier:.2f}")

@bot.callback_query_handler(func=lambda c: c.data == "mines_cashout")
def mines_cashout(c):
    uid = c.from_user.id
    game = db_query("SELECT state FROM mines_games WHERE user_id=?", (uid,), True)
    if not game:
        bot.answer_callback_query(c.id, "Нет активной игры")
        return
    game_state = json.loads(game[0][0])
    if game_state["status"] != "active":
        bot.answer_callback_query(c.id, "Игра завершена")
        return
    prize = int(game_state["bet"] * game_state["multiplier"])
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
    bot.send_message(c.message.chat.id, f"💰 Вы забрали выигрыш: {prize} 🪙 (Множитель {game_state['multiplier']:.2f})")
    update_stats(uid, "mines", True, game_state['bet'])
    db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
    bot.answer_callback_query(c.id, "Выигрыш получен")
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
        for qid in [1,2,3,4,5,6,7]:
            db_query("INSERT OR IGNORE INTO user_quests (user_id, quest_id) VALUES (?,?)", (uid, qid))
    if not check_sub(m): return
    bot.send_message(m.chat.id, "🦾 S.P.I.R.A. v29.0", reply_markup=main_kb())

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
    bot.send_message(m.chat.id, "Доступные кейсы:\n/case_open case1 (5000🪙)\n/case_open case2 (15000🪙)\n/case_open case3 (50000🪙)")

@bot.message_handler(commands=['case_open'])
def case_open(m):
    args = m.text.split()
    if len(args)<2:
        bot.reply_to(m, "Укажите кейс: case1, case2, case3")
        return
    case_id = args[1]
    uid = m.from_user.id
    u = get_u(uid)
    case_data, _ = db_query("SELECT price, items FROM cases WHERE id=?", (case_id,), True)
    if not case_data:
        return bot.reply_to(m, "Кейс не найден")
    price, items_json = case_data[0]
    if u['bal'] < price:
        return bot.reply_to(m, "Недостаточно монет")
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (price, uid))
    items = json.loads(items_json)
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
    bot.reply_to(m, f"🎁 Вы открыли кейс {case_id} и получили {chosen}!")
    # Обновляем квест на открытие кейсов
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='open_cases') AND completed=0", (uid,))

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop_btn(m):
    items, _ = db_query("SELECT id, name_ru, price FROM shop_items WHERE price>0", fetch=True)
    if items:
        text = "🛒 Магазин:\n"
        for i,n,p in items:
            text += f"{n} - {p} 🪙 (купить /buy {i})\n"
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
    item, _ = db_query("SELECT price, type FROM shop_items WHERE id=?", (item_id,), True)
    if not item: return bot.reply_to(m, "Товар не найден")
    price, typ = item[0]
    if u['bal'] < price: return bot.reply_to(m, "Недостаточно монет")
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (price, uid))
    if typ == "role":
        # Префикс: применяем сразу
        db_query("UPDATE users SET prefix = ? WHERE id=?", (item_id, uid))
        bot.reply_to(m, f"✅ Вы купили и активировали префикс {item_id}!")
    else:
        db_query("INSERT INTO inventory (user_id, item_id, quantity) VALUES (?,?,1) ON CONFLICT(user_id,item_id) DO UPDATE SET quantity = quantity+1", (uid, item_id))
        bot.reply_to(m, f"✅ Вы купили {item_id} в инвентарь")
    # Квест на покупку префикса
    if typ == "role":
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='buy_prefix') AND completed=0", (uid,))

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
    stats, _ = db_query("SELECT total_games, total_wins, game_dice_wins, game_coin_wins, game_slots_wins, game_casino_wins, game_tic_tac_toe_wins, game_mines_wins FROM stats WHERE user_id=?", (uid,), True)
    if stats:
        s = stats[0]
        text = f"📊 Статистика:\nВсего игр: {s[0]}\nПобед: {s[1]}\n\n🎲 dice: {s[2]}\n🪙 coin: {s[3]}\n🎰 slots: {s[4]}\n🎰 casino: {s[5]}\n❌⭕ tic-tac-toe: {s[6]}\n💣 mines: {s[7]}"
        bot.send_message(m.chat.id, text)
    else:
        bot.send_message(m.chat.id, "Нет статистики")

# TTS и Imagine (без изменений)
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

# ======================== ТУРНИРЫ (сокращённо) ========================
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

# ======================== АУКЦИОН (упрощённо) ========================
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

# ======================== ГИЛЬДИИ (упрощённо) ========================
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

# ======================== ОБЩИЙ ОБРАБОТЧИК ========================
@bot.message_handler(content_types=['text'])
def text_handler(m):
    if not check_sub(m): return
    uid = m.from_user.id
    u = get_u(uid)
    if not u:
        bot.reply_to(m, "/start")
        return
    # Нет нейросети, просто игнорируем неизвестные тексты
    if m.text not in ["🎮 Игры","💰 Баланс","👤 Профиль","👥 Рефералы","🏆 ТОП","🎟 Промокод","📦 Кейсы","🛒 Магазин","⚙️ Бонус","🎲 Статистика","🏅 Инвентарь","🎤 TTS","🎨 Imagine","🏟 Турнир","⚔️ Аукцион","📜 Задания","🏛 Гильдия"]:
        bot.send_message(m.chat.id, "Используйте кнопки меню.")

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
    db_query("INSERT OR I