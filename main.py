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
OWNER_ID = 6133141754  # Владелец бота (вы)
CHANNEL_ID = "@spiraofficial"

bot = telebot.TeleBot(TOKEN, threaded=True)

# ======================== БАЗА ДАННЫХ ========================
def db_query(query, params=(), fetch=False):
    conn = None
    try:
        conn = sqlite3.connect('spira_final.db', timeout=30, check_same_thread=False)
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

# Таблицы (добавлена таблица admin_users)
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
db_query("""CREATE TABLE IF NOT EXISTS admin_users (
    user_id INTEGER PRIMARY KEY,
    added_by INTEGER
)""")
db_query("""CREATE TABLE IF NOT EXISTS stats (
    user_id INTEGER PRIMARY KEY,
    total_games INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    game_dice_wins INTEGER DEFAULT 0,
    game_coin_wins INTEGER DEFAULT 0,
    game_slots_wins INTEGER DEFAULT 0,
    game_casino_wins INTEGER DEFAULT 0,
    game_tic_tac_toe_wins INTEGER DEFAULT 0,
    game_mines_wins INTEGER DEFAULT 0,
    game_basketball_wins INTEGER DEFAULT 0
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
db_query("CREATE TABLE IF NOT EXISTS ttt_games (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, player1 INTEGER, player2 INTEGER, board TEXT, turn INTEGER, status TEXT, bet INTEGER, winner_id INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS mines_games (user_id INTEGER, state TEXT)")

# Наполнение начальными данными (магазин, кейсы, задания, промокод)
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
db_query("INSERT OR IGNORE INTO shop_items VALUES ('boost1','Буст +20%',5000,'boost','win_chance+20')")
db_query("INSERT OR IGNORE INTO shop_items VALUES ('skin_gold','Золотой кубик',10000,'skin','dice_emoji=🎲✨')")

db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"prefix_winner\",\"prob\":0.3},{\"item\":\"boost1\",\"prob\":0.7}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case2','Редкий кейс',15000,'[{\"item\":\"prefix_legend\",\"prob\":0.2},{\"item\":\"prefix_king\",\"prob\":0.3},{\"item\":\"skin_gold\",\"prob\":0.5}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case3','Легендарный кейс',50000,'[{\"item\":\"prefix_god\",\"prob\":0.1},{\"item\":\"prefix_dragon\",\"prob\":0.2},{\"item\":\"prefix_immortal\",\"prob\":0.7}]')")

quests_data = [
    (1, 'Сыграй 5 игр', 'play_games', 5, 1000, 50, ''),
    (2, 'Выиграй 3 игры', 'win_games', 3, 2000, 100, 'prefix_winner'),
    (3, 'Открой 2 кейса', 'open_cases', 2, 3000, 150, 'prefix_lucky'),
    (4, 'Купи 1 префикс', 'buy_prefix', 1, 5000, 200, 'prefix_master'),
    (5, 'Пригласи друга', 'referral', 1, 10000, 300, 'prefix_rich'),
    (6, 'Выиграй в крестики-нолики', 'ttt_win', 3, 4000, 150, 'prefix_pro'),
    (7, 'Сыграй в мины 5 раз', 'play_mines', 5, 3000, 100, 'prefix_gambler'),
]
for q in quests_data:
    db_query("INSERT OR IGNORE INTO quests VALUES (?,?,?,?,?,?,?)", q)

db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024', 10000, 50, 0)")
db_query("INSERT OR IGNORE INTO promo VALUES ('TEST500', 500, 100, 0)")

# Добавляем владельца в админы (если ещё нет)
db_query("INSERT OR IGNORE INTO admin_users VALUES (?,?)", (OWNER_ID, OWNER_ID))

logger.info("База данных инициализирована")# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def is_admin(user_id):
    """Проверяет, является ли пользователь админом (владелец или добавленный)"""
    if user_id == OWNER_ID:
        return True
    res, _ = db_query("SELECT user_id FROM admin_users WHERE user_id=?", (user_id,), True)
    return bool(res)

def get_user(uid):
    res, _ = db_query("SELECT balance, mode, prefix, level, exp, lang FROM users WHERE id=?", (uid,), True)
    if res:
        return {
            "bal": res[0][0],
            "mode": res[0][1],
            "prefix": res[0][2] or "Новичок 🛡",
            "level": res[0][3],
            "exp": res[0][4],
            "lang": res[0][5] or "ru"
        }
    return None

def get_user_prefix(uid):
    user = get_user(uid)
    return user['prefix'] if user else "Новичок 🛡"

def is_group_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def update_stats(uid, game, win, bet=0):
    exp_gain = bet // 100 + 1 if win else 1
    db_query("UPDATE users SET exp = exp + ? WHERE id=?", (exp_gain, uid))
    u = get_user(uid)
    if u and u['exp'] >= u['level'] * 100:
        new_level = u['level'] + 1
        db_query("UPDATE users SET level = ?, exp = 0 WHERE id=?", (new_level, uid))
        try:
            bot.send_message(uid, f"🎉 Поздравляем! Вы достигли {new_level} уровня!")
        except:
            pass

    stats, _ = db_query("SELECT * FROM stats WHERE user_id=?", (uid,), True)
    if not stats:
        db_query("INSERT INTO stats (user_id) VALUES (?)", (uid,))
        stats = [(0, 0, 0, 0, 0, 0, 0, 0, 0)]

    total_games = (stats[0][1] or 0) + 1
    total_wins = (stats[0][2] or 0) + (1 if win else 0)
    game_cols = {
        'dice': 'game_dice_wins',
        'coin': 'game_coin_wins',
        'slots': 'game_slots_wins',
        'casino': 'game_casino_wins',
        'ttt': 'game_tic_tac_toe_wins',
        'mines': 'game_mines_wins',
        'basketball': 'game_basketball_wins'
    }
    col = game_cols.get(game, 'game_dice_wins')
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, {col} = {col} + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))

    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))

    qs, _ = db_query("""SELECT q.id, q.reward_coins, q.reward_exp, q.reward_prefix
                        FROM user_quests uq
                        JOIN quests q ON uq.quest_id = q.id
                        WHERE uq.user_id=? AND uq.completed=0 AND uq.progress >= q.goal_count""", (uid,), True)
    for qid, coins, exp, prefix_item in qs:
        db_query("UPDATE user_quests SET completed=1 WHERE user_id=? AND quest_id=?", (uid, qid))
        db_query("UPDATE users SET balance = balance + ?, exp = exp + ? WHERE id=?", (coins, exp, uid))
        if prefix_item:
            db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, prefix_item))
            try:
                bot.send_message(uid, f"✅ Задание выполнено! +{coins}🪙 +{exp}⭐ + префикс {prefix_item}")
            except:
                pass
        else:
            try:
                bot.send_message(uid, f"✅ Задание выполнено! +{coins}🪙 +{exp}⭐")
            except:
                pass

def check_subscription(message):
    if message.chat.type != 'private':
        return True
    try:
        status = bot.get_chat_member(CHANNEL_ID, message.from_user.id).status
        if status in ['member', 'administrator', 'creator']:
            return True
    except:
        pass
    bot.send_message(message.chat.id, f"⚠️ Подпишитесь на {CHANNEL_ID} для использования бота.")
    return False

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    markup.add("⚙️ Бонус", "🎲 Статистика", "🏅 Инвентарь", "🎤 TTS", "🎨 Imagine")
    markup.add("🏟 Турнир", "⚔️ Аукцион", "📜 Задания", "🏛 Гильдия", "➕ Добавить бота в чат")
    return markup# ======================== ИГРЫ (inline меню) ========================
@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games_menu(message):
    games = ["dice", "coin", "slots", "casino", "basketball", "ttt", "mines"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for g in games:
        markup.add(types.InlineKeyboardButton(g.capitalize(), callback_data=f"game_{g}"))
    bot.send_message(message.chat.id, "🎲 Выберите игру:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def game_callback(call):
    game = call.data.split("_")[1]
    if game == "ttt":
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bet in [100, 500, 1000, 5000]:
            markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"ttt_bet_{bet}"))
        bot.edit_message_text("Выберите ставку для крестиков-ноликов:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif game == "mines":
        markup = types.InlineKeyboardMarkup(row_width=5)
        for mines in range(1, 11):
            markup.add(types.InlineKeyboardButton(str(mines), callback_data=f"mines_mines_{mines}"))
        bot.edit_message_text("Сколько мин? (1-10):", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bet in [100, 500, 1000, 5000]:
            markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"bet_{game}_{bet}"))
        bot.edit_message_text(f"Ставка для {game}:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("bet_"))
def simple_bet_callback(call):
    _, game, bet = call.data.split("_")
    bet = int(bet)
    uid = call.from_user.id
    user = get_user(uid)
    if not user:
        bot.answer_callback_query(call.id, "Напишите /start")
        return
    if user['bal'] < bet:
        bot.answer_callback_query(call.id, "Недостаточно монет")
        return
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    win, coeff = False, 2.0
    try:
        if game == "dice":
            val = bot.send_dice(call.message.chat.id, "🎲").dice.value
            if val >= 4:
                win = True
        elif game == "coin":
            win = random.choice([True, False])
            bot.send_message(call.message.chat.id, "🪙 Орел!" if win else "🪙 Решка!")
        elif game == "slots":
            val = bot.send_dice(call.message.chat.id, "🎰").dice.value
            if val in (1, 22, 43, 64):
                win, coeff = True, 10.0
            elif val in (16, 32, 48):
                win, coeff = True, 3.0
        elif game == "casino":
            val = bot.send_dice(call.message.chat.id, "🎰").dice.value
            if val in (1, 22, 43, 64):
                win, coeff = True, 10.0
            elif val in (16, 32, 48):
                win, coeff = True, 3.0
        elif game == "basketball":
            val = bot.send_dice(call.message.chat.id, "🏀").dice.value
            if val >= 4:
                win = True
        if win:
            prize = int(bet * coeff)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
            bot.send_message(call.message.chat.id, f"✅ Выигрыш: {prize} 🪙")
        else:
            bot.send_message(call.message.chat.id, "❌ Проигрыш")
        update_stats(uid, game, win, bet)
    except Exception as e:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, uid))
        bot.send_message(call.message.chat.id, f"Ошибка игры: {e}")
    bot.answer_callback_query(call.id)# -------------------- Крестики-нолики --------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("ttt_bet_"))
def ttt_bet_callback(call):
    bet = int(call.data.split("_")[2])
    uid = call.from_user.id
    user = get_user(uid)
    if not user or user['bal'] < bet:
        bot.answer_callback_query(call.id, "Недостаточно монет")
        return
    msg = bot.send_message(call.message.chat.id, "Введите Telegram ID или username противника, или 'бот' для игры с ботом.")
    bot.register_next_step_handler(msg, lambda m: ttt_opponent(m, bet, uid))

def ttt_opponent(message, bet, uid):
    text = message.text.strip()
    if text.lower() == "бот":
        start_ttt_game(message.chat.id, uid, None, bet)
    else:
        try:
            if text.startswith("@"):
                opponent = bot.get_chat(text).id
            else:
                opponent = int(text)
        except:
            bot.send_message(message.chat.id, "Неверный ID или username.")
            return
        if opponent == uid:
            bot.send_message(message.chat.id, "Нельзя играть с самим собой.")
            return
        opp_user = get_user(opponent)
        if not opp_user:
            bot.send_message(message.chat.id, "Противник не зарегистрирован.")
            return
        if opp_user['bal'] < bet:
            bot.send_message(message.chat.id, "У противника недостаточно монет.")
            return
        start_ttt_game(message.chat.id, uid, opponent, bet)

def start_ttt_game(chat_id, player1, player2, bet):
    board = [" " for _ in range(9)]
    turn = 1  # 1 = X (игрок1), 2 = O (игрок2 или бот)
    status = "active"
    db_query("INSERT INTO ttt_games (chat_id, player1, player2, board, turn, status, bet) VALUES (?,?,?,?,?,?,?)",
             (chat_id, player1, player2, json.dumps(board), turn, status, bet))
    game_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
    send_ttt_board(chat_id, game_id, player1, player2, board, turn, bet)

def send_ttt_board(chat_id, game_id, p1, p2, board, turn, bet):
    text = f"🎮 Крестики-нолики | Ставка: {bet} 🪙\n"
    if p2:
        text += f"X: {p1}  |  O: {p2}\n"
    else:
        text += f"X: {p1}  |  O: Бот\n"
    text += f"Ход: {'❌' if turn == 1 else '⭕'}\n\n"
    markup = types.InlineKeyboardMarkup(row_width=3)
    for i in range(9):
        symbol = board[i]
        if symbol == " ":
            button_text = "⬜"
        elif symbol == "X":
            button_text = "❌"
        else:
            button_text = "⭕"
        callback = f"ttt_move_{game_id}_{i}"
        markup.add(types.InlineKeyboardButton(button_text, callback_data=callback))
    bot.edit_message_text(text, chat_id, message_id=None, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ttt_move_"))
def ttt_move_callback(call):
    _, game_id, pos = call.data.split("_")
    game_id = int(game_id)
    pos = int(pos)
    uid = call.from_user.id
    game = db_query("SELECT player1, player2, board, turn, status, bet FROM ttt_games WHERE id=?", (game_id,), True)
    if not game:
        bot.answer_callback_query(call.id, "Игра не найдена")
        return
    p1, p2, board_json, turn, status, bet = game[0]
    if status != "active":
        bot.answer_callback_query(call.id, "Игра уже завершена")
        return
    board = json.loads(board_json)
    if turn == 1 and uid != p1:
        bot.answer_callback_query(call.id, "Сейчас не ваш ход")
        return
    if turn == 2 and p2 and uid != p2:
        bot.answer_callback_query(call.id, "Сейчас не ваш ход")
        return
    if p2 is None and turn == 2:
        bot.answer_callback_query(call.id, "Сейчас ходит бот")
        return
    if board[pos] != " ":
        bot.answer_callback_query(call.id, "Клетка уже занята")
        return
    # Ход игрока
    board[pos] = "X" if turn == 1 else "O"
    winner = check_ttt_winner(board)
    if winner:
        winner_id = p1 if winner == "X" else p2
        if winner_id:
            prize = int(bet * 1.8)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, winner_id))
            bot.edit_message_text(f"🏆 Игрок {winner_id} выиграл {prize} 🪙!", call.message.chat.id, call.message.message_id)
            update_stats(winner_id, "ttt", True, bet)
            if p2 and p2 != winner_id:
                update_stats(p2, "ttt", False, bet)
            else:
                update_stats(p1, "ttt", False, bet)
        else:
            # победа бота
            prize = int(bet * 1.8)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, p1))
            bot.edit_message_text(f"🤖 Бот выиграл! Вы потеряли {bet} 🪙.", call.message.chat.id, call.message.message_id)
            update_stats(p1, "ttt", False, bet)
        db_query("UPDATE ttt_games SET status='finished', winner_id=? WHERE id=?", (winner_id, game_id))
        return
    if " " not in board:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p1))
        if p2:
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p2))
            bot.edit_message_text("🤝 Ничья! Ставки возвращены.", call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_text("🤝 Ничья с ботом! Ставка возвращена.", call.message.chat.id, call.message.message_id)
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    new_turn = 2 if turn == 1 else 1
    db_query("UPDATE ttt_games SET board=?, turn=? WHERE id=?", (json.dumps(board), new_turn, game_id))
    if p2 is None and new_turn == 2:
        # Ход бота
        bot.answer_callback_query(call.id, "Бот ходит...")
        bot_move(game_id)
    else:
        send_ttt_board(call.message.chat.id, game_id, p1, p2, board, new_turn, bet)
    bot.answer_callback_query(call.id)

def check_ttt_winner(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] == board[b] == board[c] and board[a] != " ":
            return board[a]
    return None

def bot_move(game_id):
    game = db_query("SELECT player1, board, turn, bet, chat_id, message_id FROM ttt_games WHERE id=?", (game_id,), True)
    if not game:
        return
    p1, board_json, turn, bet, chat_id, msg_id = game[0]
    if turn != 2:
        return
    board = json.loads(board_json)
    empty = [i for i, cell in enumerate(board) if cell == " "]
    if not empty:
        return
    pos = random.choice(empty)
    board[pos] = "O"
    winner = check_ttt_winner(board)
    if winner:
        db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, p1))
        bot.send_message(p1, f"🤖 Бот выиграл! Вы потеряли {bet} 🪙.")
        update_stats(p1, "ttt", False, bet)
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    if " " not in board:
        db_query("UPDATE users SET balance = balance + ? WHERE id=?", (bet, p1))
        bot.send_message(p1, "🤝 Ничья с ботом! Ставка возвращена.")
        db_query("UPDATE ttt_games SET status='finished' WHERE id=?", (game_id,))
        return
    db_query("UPDATE ttt_games SET board=?, turn=1 WHERE id=?", (json.dumps(board), game_id))
    send_ttt_board(chat_id, game_id, p1, None, board, 1, bet)# -------------------- Игра "Мины" --------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("mines_mines_"))
def mines_mines_callback(call):
    mines = int(call.data.split("_")[2])
    uid = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bet in [100, 500, 1000, 5000]:
        markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"mines_bet_{mines}_{bet}"))
    bot.edit_message_text(f"Выберите ставку для игры с {mines} минами:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mines_bet_"))
def mines_bet_callback(call):
    _, mines, bet = call.data.split("_")
    mines = int(mines)
    bet = int(bet)
    uid = call.from_user.id
    user = get_user(uid)
    if not user or user['bal'] < bet:
        bot.answer_callback_query(call.id, "Недостаточно монет")
        return
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (bet, uid))
    total_cells = 25
    bomb_positions = random.sample(range(total_cells), mines)
    game_state = {
        "board": ["?"] * 25,
        "bombs": bomb_positions,
        "revealed": [],
        "multiplier": 1.0,
        "bet": bet,
        "status": "active"
    }
    db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
    db_query("INSERT INTO mines_games VALUES (?,?)", (uid, json.dumps(game_state)))
    send_mines_board(call.message.chat.id, uid, game_state)
    bot.answer_callback_query(call.id)

def send_mines_board(chat_id, uid, game_state):
    board = game_state["board"]
    text = f"💣 Игра Мины | Ставка: {game_state['bet']} 🪙 | Множитель: {game_state['multiplier']:.2f}x\n\n"
    # Отображаем сетку 5x5
    markup = types.InlineKeyboardMarkup(row_width=5)
    for i in range(25):
        if board[i] == "?":
            markup.add(types.InlineKeyboardButton("❓", callback_data=f"mines_open_{i}"))
        elif board[i] == "💣":
            markup.add(types.InlineKeyboardButton("💣", callback_data="mines_no"))
        elif board[i] == "💰":
            markup.add(types.InlineKeyboardButton("💰", callback_data="mines_no"))
        else:
            markup.add(types.InlineKeyboardButton(" ", callback_data="mines_no"))
    markup.add(types.InlineKeyboardButton("💰 Забрать выигрыш", callback_data="mines_cashout"))
    bot.edit_message_text(text, chat_id, message_id=None, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mines_open_"))
def mines_open_callback(call):
    pos = int(call.data.split("_")[2])
    uid = call.from_user.id
    game = db_query("SELECT state FROM mines_games WHERE user_id=?", (uid,), True)
    if not game:
        bot.answer_callback_query(call.id, "Нет активной игры")
        return
    game_state = json.loads(game[0][0])
    if game_state["status"] != "active":
        bot.answer_callback_query(call.id, "Игра завершена")
        return
    if pos in game_state["revealed"]:
        bot.answer_callback_query(call.id, "Клетка уже открыта")
        return
    if pos in game_state["bombs"]:
        game_state["board"][pos] = "💣"
        bot.edit_message_text(f"💥 Вы наступили на мину! Проигрыш {game_state['bet']} 🪙", call.message.chat.id, call.message.message_id)
        db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
        update_stats(uid, "mines", False, game_state['bet'])
        bot.answer_callback_query(call.id, "Проигрыш")
        return
    game_state["board"][pos] = "💰"
    game_state["revealed"].append(pos)
    safe_cells = 25 - len(game_state["bombs"])
    multiplier = 1 + (len(game_state["revealed"]) / safe_cells) * 2.0
    game_state["multiplier"] = multiplier
    db_query("UPDATE mines_games SET state=? WHERE user_id=?", (json.dumps(game_state), uid))
    send_mines_board(call.message.chat.id, uid, game_state)
    bot.answer_callback_query(call.id, f"Клетка безопасна! Множитель {multiplier:.2f}")

@bot.callback_query_handler(func=lambda call: call.data == "mines_cashout")
def mines_cashout_callback(call):
    uid = call.from_user.id
    game = db_query("SELECT state FROM mines_games WHERE user_id=?", (uid,), True)
    if not game:
        bot.answer_callback_query(call.id, "Нет активной игры")
        return
    game_state = json.loads(game[0][0])
    if game_state["status"] != "active":
        bot.answer_callback_query(call.id, "Игра завершена")
        return
    prize = int(game_state["bet"] * game_state["multiplier"])
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, uid))
    bot.edit_message_text(f"💰 Вы забрали выигрыш: {prize} 🪙 (Множитель {game_state['multiplier']:.2f})", call.message.chat.id, call.message.message_id)
    update_stats(uid, "mines", True, game_state['bet'])
    db_query("DELETE FROM mines_games WHERE user_id=?", (uid,))
    bot.answer_callback_query(call.id, "Выигрыш получен")# ======================== ОСНОВНЫЕ КОМАНДЫ ========================
@bot.message_handler(commands=['start'])
def start_command(message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user:
        ref = None
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref = args[1]
        db_query("INSERT INTO users (id, name, balance, ref_id, prefix) VALUES (?,?,?,?,?)",
                 (uid, message.from_user.first_name, 5000, ref, 'Новичок 🛡'))
        if ref and int(ref) != uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id=?", (ref,))
            try:
                bot.send_message(ref, "🎁 +5000 🪙 за реферала!")
            except:
                pass
        for qid in range(1, 8):
            db_query("INSERT OR IGNORE INTO user_quests (user_id, quest_id) VALUES (?,?)", (uid, qid))
    if message.chat.type == 'private':
        if not check_subscription(message):
            return
        bot.send_message(message.chat.id, "🦾 S.P.I.R.A. v31.0", reply_markup=main_keyboard())
    else:
        bot.send_message(message.chat.id, "🦾 Бот активен!")

@bot.message_handler(func=lambda m: m.text == "➕ Добавить бота в чат" and m.chat.type == 'private')
def add_bot_to_chat(message):
    bot_username = bot.get_me().username
    url = f"https://t.me/{bot_username}?startgroup=start"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить в группу", url=url))
    bot.send_message(message.chat.id, "Нажмите кнопку, чтобы добавить бота в чат:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Баланс")
def balance_button(message):
    user = get_user(message.from_user.id)
    if user:
        bot.reply_to(message, f"💰 Ваш баланс: {user['bal']} 🪙")
    else:
        bot.reply_to(message, "Напишите /start")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_button(message):
    user = get_user(message.from_user.id)
    if not user:
        bot.reply_to(message, "/start")
        return
    text = (f"👤 {message.from_user.first_name}\n"
            f"🏷 Звание: {user['prefix']}\n"
            f"📊 Уровень: {user['level']}\n"
            f"⭐ Опыт: {user['exp']}/{user['level']*100}\n"
            f"💰 Баланс: {user['bal']} 🪙")
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎭 Выбрать префикс", callback_data="choose_prefix"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "choose_prefix")
def choose_prefix_callback(call):
    uid = call.from_user.id
    inv, _ = db_query("SELECT item_id FROM inventory WHERE user_id=? AND item_id IN (SELECT id FROM shop_items WHERE type='role')", (uid,), True)
    if not inv:
        bot.answer_callback_query(call.id, "У вас нет купленных префиксов. Купите в магазине!")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for item in inv:
        name, _ = db_query("SELECT name_ru FROM shop_items WHERE id=?", (item[0],), True)
        if name:
            markup.add(types.InlineKeyboardButton(name[0][0], callback_data=f"setprefix_{item[0]}"))
    bot.edit_message_text("Выберите префикс для отображения:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setprefix_"))
def set_prefix_callback(call):
    prefix_id = call.data.split("_")[1]
    uid = call.from_user.id
    inv, _ = db_query("SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (uid, prefix_id), True)
    if not inv:
        bot.answer_callback_query(call.id, "У вас нет этого префикса")
        return
    name, _ = db_query("SELECT name_ru FROM shop_items WHERE id=?", (prefix_id,), True)
    prefix_name = name[0][0] if name else "Префикс"
    db_query("UPDATE users SET prefix=? WHERE id=?", (prefix_name, uid))
    bot.answer_callback_query(call.id, f"✅ Префикс '{prefix_name}' установлен!")
    bot.send_message(call.message.chat.id, f"Ваше новое звание: {prefix_name}")

@bot.message_handler(func=lambda m: m.text == "🏆 ТОП")
def top_button(message):
    # Исключаем владельца из топа
    data, _ = db_query("SELECT name, balance FROM users WHERE id != ? ORDER BY balance DESC LIMIT 10", (OWNER_ID,), fetch=True)
    if data:
        text = "🏆 ТОП-10 богачей:\n" + "\n".join([f"{i+1}. {row[0]}: {row[1]} 🪙" for i, row in enumerate(data)])
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "Нет данных")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_button(message):
    username = bot.get_me().username
    if username:
        link = f"https://t.me/{username}?start={message.from_user.id}"
        bot.send_message(message.chat.id, f"🔗 Ваша реферальная ссылка:\n{link}\nЗа каждого друга +5000 🪙")
    else:
        bot.send_message(message.chat.id, "У бота нет username")

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_button(message):
    msg = bot.send_message(message.chat.id, "Введите промокод:")
    bot.register_next_step_handler(msg, apply_promo)

def apply_promo(message):
    uid = message.from_user.id
    code = message.text.strip().upper()
    # Проверяем, использовал ли уже
    if db_query("SELECT * FROM used_promos WHERE user_id=? AND code=?", (uid, code), True)[0]:
        bot.reply_to(message, "❌ Вы уже использовали этот промокод.")
        return
    promo = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code=?", (code,), True)
    if not promo:
        bot.reply_to(message, "❌ Неверный промокод.")
        return
    reward, limit, used = promo[0]
    if used >= limit:
        bot.reply_to(message, "❌ Лимит использований этого промокода исчерпан.")
        return
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (reward, uid))
    db_query("UPDATE promo SET used_count = used_count + 1 WHERE code=?", (code,))
    db_query("INSERT INTO used_promos VALUES (?,?)", (uid, code))
    bot.reply_to(message, f"✅ Промокод активирован! Вы получили {reward} 🪙.")

@bot.message_handler(func=lambda m: m.text == "📦 Кейсы")
def cases_button(message):
    bot.send_message(message.chat.id, "Доступные кейсы:\n/case_open case1 (5000🪙)\n/case_open case2 (15000🪙)\n/case_open case3 (50000🪙)")

@bot.message_handler(commands=['case_open'])
def open_case(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Укажите кейс: case1, case2, case3")
        return
    case_id = args[1]
    uid = message.from_user.id
    user = get_user(uid)
    case_data, _ = db_query("SELECT price, items FROM cases WHERE id=?", (case_id,), True)
    if not case_data:
        bot.reply_to(message, "Кейс не найден")
        return
    price, items_json = case_data[0]
    if user['bal'] < price:
        bot.reply_to(message, "Недостаточно монет")
        return
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
    bot.reply_to(message, f"🎁 Вы открыли кейс {case_id} и получили {chosen}!")
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='open_cases') AND completed=0", (uid,))

@bot.message_handler(func=lambda m: m.text == "🛒 Магазин")
def shop_button(message):
    items, _ = db_query("SELECT id, name_ru, price FROM shop_items WHERE price>0", fetch=True)
    if items:
        text = "🛒 Магазин:\n"
        for i, n, p in items:
            text += f"{n} - {p} 🪙 (купить /buy {i})\n"
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "Магазин пуст")

@bot.message_handler(commands=['buy'])
def buy_command(message):
    uid = message.from_user.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Укажите ID товара: /buy [id]")
        return
    item_id = args[1]
    user = get_user(uid)
    item, _ = db_query("SELECT price, type FROM shop_items WHERE id=?", (item_id,), True)
    if not item:
        bot.reply_to(message, "Товар не найден")
        return
    price, typ = item[0]
    if user['bal'] < price:
        bot.reply_to(message, "Недостаточно монет")
        return
    db_query("UPDATE users SET balance = balance - ? WHERE id=?", (price, uid))
    if typ == "role":
        db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, item_id))
        if user['prefix'] == "Новичок 🛡":
            name, _ = db_query("SELECT name_ru FROM shop_items WHERE id=?", (item_id,), True)
            if name:
                db_query("UPDATE users SET prefix=? WHERE id=?", (name[0][0], uid))
                bot.reply_to(message, f"✅ Вы купили и активировали префикс {name[0][0]}!")
        else:
            bot.reply_to(message, f"✅ Вы купили префикс! Используйте /setprefix {item_id} чтобы активировать.")
    else:
        db_query("INSERT OR IGNORE INTO inventory (user_id, item_id, quantity) VALUES (?,?,1)", (uid, item_id))
        bot.reply_to(message, f"✅ Вы купили {item_id} в инвентарь")
    if typ == "role":
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='buy_prefix') AND completed=0", (uid,))

@bot.message_handler(func=lambda m: m.text == "🏅 Инвентарь")
def inventory_button(message):
    uid = message.from_user.id
    inv, _ = db_query("SELECT item_id, quantity FROM inventory WHERE user_id=?", (uid,), True)
    if inv:
        text = "📦 Ваш инвентарь:\n"
        for i, q in inv:
            name, _ = db_query("SELECT name_ru FROM shop_items WHERE id=?", (i,), True)
            item_name = name[0][0] if name else i
            text += f"{item_name} x{q}\n"
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "Инвентарь пуст")

@bot.message_handler(func=lambda m: m.text == "⚙️ Бонус")
def daily_bonus(message):
    uid = message.from_user.id
    today = datetime.now().date().isoformat()
    user = get_user(uid)
    if not user:
        bot.reply_to(message, "/start")
        return
    res, _ = db_query("SELECT daily_last, daily_streak FROM users WHERE id=?", (uid,), True)
    last, streak = res[0] if res else (None, 0)
    if last == today:
        bot.reply_to(message, "Вы уже получали бонус сегодня!")
        return
    if last == (datetime.now().date() - timedelta(days=1)).isoformat():
        streak += 1
    else:
        streak = 1
    bonus = min(500 + (streak-1)*100, 2000)
    db_query("UPDATE users SET balance = balance + ?, daily_last = ?, daily_streak = ? WHERE id=?", (bonus, today, streak, uid))
    bot.reply_to(message, f"✅ Ежедневный бонус: +{bonus} 🪙 (Стрик: {streak})")

@bot.message_handler(func=lambda m: m.text == "🎲 Статистика")
def stats_button(message):
    uid = message.from_user.id
    stats, _ = db_query("SELECT total_games, total_wins, game_dice_wins, game_coin_wins, game_slots_wins, game_casino_wins, game_tic_tac_toe_wins, game_mines_wins, game_basketball_wins FROM stats WHERE user_id=?", (uid,), True)
    if stats:
        s = stats[0]
        text = (f"📊 Ваша статистика:\n"
                f"🎲 Всего игр: {s[0]}\n"
                f"🏆 Побед: {s[1]}\n\n"
                f"🎲 dice: {s[2]}\n"
                f"🪙 coin: {s[3]}\n"
                f"🎰 slots: {s[4]}\n"
                f"🎰 casino: {s[5]}\n"
                f"❌⭕ крестики-нолики: {s[6]}\n"
                f"💣 мины: {s[7]}\n"
                f"🏀 баскетбол: {s[8]}")
        bot.send_message(message.chat.id, text)
    else:
        bot.send_message(message.chat.id, "Нет статистики")

@bot.message_handler(func=lambda m: m.text == "🎤 TTS")
def tts_button(message):
    msg = bot.send_message(message.chat.id, "Напишите текст для озвучки:")
    bot.register_next_step_handler(msg, tts_generate)

def tts_generate(message):
    if not message.text:
        return
    try:
        tts = gTTS(message.text, lang='ru')
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        bot.send_voice(message.chat.id, audio)
    except Exception as e:
        bot.reply_to(message, f"Ошибка TTS: {e}")

@bot.message_handler(func=lambda m: m.text == "🎨 Imagine")
def imagine_button(message):
    msg = bot.send_message(message.chat.id, "Опишите картинку:")
    bot.register_next_step_handler(msg, generate_image)

def generate_image(message):
    if not message.text:
        return
    bot.send_message(message.chat.id, "🎨 Генерирую изображение...")
    prompt = message.text
    for attempt in range(2):
        try:
            url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                bot.send_photo(message.chat.id, response.content, caption=f"Ваш запрос: {prompt[:100]}")
                return
        except Exception as e:
            logger.warning(f"Image attempt {attempt+1} failed: {e}")
            time.sleep(2)
    bot.send_message(message.chat.id, "Не удалось сгенерировать картинку. Попробуйте позже.")# ======================== ТУРНИРЫ ========================
@bot.message_handler(func=lambda m: m.text == "🏟 Турнир")
def tournament_menu(message):
    bot.send_message(message.chat.id, "🏆 Турнир каждые 6 часов. Участие: /tournament_join")

@bot.message_handler(commands=['tournament_join'])
def tournament_join(message):
    uid = message.from_user.id
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
        bot.reply_to(message, "Вы уже участвуете в текущем турнире.")
        return
    participants.append(uid)
    db_query("UPDATE tournaments SET participants = ? WHERE id=?", (json.dumps(participants), tid))
    bot.reply_to(message, "✅ Вы записаны на турнир!")

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
                try:
                    bot.send_message(winner, f"🏆 Вы выиграли турнир! +{prize} 🪙")
                except:
                    pass
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
def auction_menu(message):
    bot.send_message(message.chat.id, "Аукцион:\n/auction list - список лотов\n/auction sell [item] [min_bid] - выставить лот\n/auction bid [lot_id] [sum] - сделать ставку")

@bot.message_handler(commands=['auction'])
def auction_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Используйте: /auction list|sell|bid")
        return
    action = args[1].lower()
    uid = message.from_user.id
    if action == "list":
        lots, _ = db_query("SELECT id, seller_id, item_id, current_bid, end_time FROM auctions WHERE status='active'", fetch=True)
        if not lots:
            bot.reply_to(message, "Нет активных лотов")
            return
        text = "🏷 Активные лоты:\n"
        for l in lots:
            text += f"ID {l[0]}: {l[2]} | Ставка: {l[3]} | До {l[4][:16]}\n"
        bot.send_message(message.chat.id, text)
    elif action == "sell":
        if len(args) < 4:
            bot.reply_to(message, "Формат: /auction sell [item_id] [min_bid]")
            return
        item_id = args[2]
        min_bid = int(args[3])
        inv, _ = db_query("SELECT quantity FROM inventory WHERE user_id=? AND item_id=?", (uid, item_id), True)
        if not inv or inv[0][0] < 1:
            bot.reply_to(message, "У вас нет такого предмета")
            return
        end_time = (datetime.now() + timedelta(hours=24)).isoformat()
        db_query("INSERT INTO auctions (seller_id, item_id, min_bid, current_bid, end_time) VALUES (?,?,?,?,?)",
                 (uid, item_id, min_bid, min_bid, end_time))
        bot.reply_to(message, f"Лот {item_id} выставлен на 24 часа")
    elif action == "bid":
        if len(args) < 4:
            bot.reply_to(message, "Формат: /auction bid [lot_id] [сумма]")
            return
        lot_id = int(args[2])
        bid = int(args[3])
        lot, _ = db_query("SELECT seller_id, current_bid FROM auctions WHERE id=? AND status='active'", (lot_id,), True)
        if not lot:
            bot.reply_to(message, "Лот не найден")
            return
        seller, curr = lot[0]
        if uid == seller:
            bot.reply_to(message, "Нельзя торговаться за свой лот")
            return
        if bid <= curr:
            bot.reply_to(message, f"Ставка должна быть больше {curr}")
            return
        user = get_user(uid)
        if user['bal'] < bid:
            bot.reply_to(message, "Недостаточно монет")
            return
        db_query("UPDATE auctions SET current_bid=?, current_bidder=? WHERE id=?", (bid, uid, lot_id))
        bot.reply_to(message, f"Ставка {bid} принята!")

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
                except:
                    pass
            db_query("UPDATE auctions SET status='finished' WHERE id=?", (aid,))

# ======================== ЗАДАНИЯ ========================
@bot.message_handler(func=lambda m: m.text == "📜 Задания")
def quests_button(message):
    uid = message.from_user.id
    quests, _ = db_query("SELECT id, name_ru, goal_count FROM quests", fetch=True)
    user_q, _ = db_query("SELECT quest_id, progress, completed FROM user_quests WHERE user_id=?", (uid,), True)
    prog = {q[0]: (q[1], q[2]) for q in user_q}
    text = "📜 Ваши задания:\n"
    for qid, name, goal in quests:
        p, done = prog.get(qid, (0, 0))
        status = "✅" if done else f"{p}/{goal}"
        text += f"{status} {name}\n"
    bot.send_message(message.chat.id, text)

# ======================== ГИЛЬДИИ ========================
@bot.message_handler(func=lambda m: m.text == "🏛 Гильдия")
def guild_menu(message):
    bot.send_message(message.chat.id, "Гильдии:\n/guild create [название]\n/guild join [id]\n/guild info [id]\n/guild leave")

@bot.message_handler(commands=['guild'])
def guild_command(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Используйте: /guild create|join|info|leave")
        return
    action = args[1].lower()
    uid = message.from_user.id
    if action == "create":
        if len(args) < 3:
            bot.reply_to(message, "Укажите название гильдии")
            return
        name = " ".join(args[2:])
        db_query("INSERT INTO guilds (name, leader_id, created) VALUES (?,?,?)", (name, uid, datetime.now().isoformat()))
        gid = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
        db_query("INSERT INTO guild_members VALUES (?,?,?)", (uid, gid, "leader"))
        bot.reply_to(message, f"Гильдия {name} создана! ID: {gid}")
    elif action == "join":
        if len(args) < 3:
            bot.reply_to(message, "Укажите ID гильдии")
            return
        gid = int(args[2])
        member, _ = db_query("SELECT user_id FROM guild_members WHERE user_id=? AND guild_id=?", (uid, gid), True)
        if member:
            bot.reply_to(message, "Вы уже состоите в этой гильдии")
            return
        db_query("INSERT INTO guild_members VALUES (?,?,?)", (uid, gid, "member"))
        bot.reply_to(message, f"Вы вступили в гильдию {gid}")
    elif action == "info":
        if len(args) < 3:
            bot.reply_to(message, "Укажите ID гильдии")
            return
        gid = int(args[2])
        guild, _ = db_query("SELECT name, leader_id, balance, level FROM guilds WHERE id=?", (gid,), True)
        if not guild:
            bot.reply_to(message, "Гильдия не найдена")
            return
        name, lid, bal, lvl = guild[0]
        cnt, _ = db_query("SELECT COUNT(*) FROM guild_members WHERE guild_id=?", (gid,), True)
        bot.send_message(message.chat.id, f"🏛 {name}\nЛидер: {lid}\nУровень: {lvl}\nКазна: {bal}\nУчастников: {cnt[0][0]}")
    elif action == "leave":
        db_query("DELETE FROM guild_members WHERE user_id=? AND guild_id IN (SELECT id FROM guilds WHERE leader_id!=?)", (uid, uid))
        bot.reply_to(message, "Вы покинули гильдию")# ======================== ОБРАБОТКА СООБЩЕНИЙ В ГРУППАХ ========================
@bot.message_handler(func=lambda m: m.chat.type != 'private' and m.text and not m.text.startswith('/'))
def group_message_handler(message):
    """В группе бот показывает префикс пользователя (если не админ)"""
    uid = message.from_user.id
    if is_group_admin(message.chat.id, uid):
        role_text = "[Админ]"
    else:
        prefix = get_user_prefix(uid)
        role_text = f"[{prefix}]"
    # Для отображения можно раскомментировать строку ниже, но лучше не спамить
    # bot.reply_to(message, f"{role_text} {message.text}")
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        time.sleep(0.5)
    except:
        pass

# ======================== АДМИН-ПАНЕЛЬ (с добавлением админов) ========================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    text = "👑 Админ-панель:\n"
    text += "/broadcast [текст]\n"
    text += "/give [id] [сумма]\n"
    text += "/createpromo [код] [награда] [лимит]\n"
    text += "/ban [id]\n"
    text += "/addadmin [id]  (только для владельца)"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "Только владелец бота может назначать админов.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Формат: /addadmin [user_id]")
        return
    new_admin = int(args[1])
    if new_admin == OWNER_ID:
        bot.reply_to(message, "Владелец уже админ.")
        return
    db_query("INSERT OR IGNORE INTO admin_users VALUES (?,?)", (new_admin, OWNER_ID))
    bot.reply_to(message, f"Пользователь {new_admin} теперь админ.")
    try:
        bot.send_message(new_admin, "🎉 Вы стали администратором бота! Используйте /admin для списка команд.")
    except:
        pass

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if not is_admin(message.from_user.id):
        return
    text = message.text.replace("/broadcast ", "")
    if not text:
        bot.reply_to(message, "Введите текст рассылки")
        return
    users, _ = db_query("SELECT id FROM users", fetch=True)
    count = 0
    for uid in users:
        try:
            bot.send_message(uid[0], f"📢 {text}")
            count += 1
        except:
            pass
    bot.reply_to(message, f"Рассылка отправлена {count} пользователям")

@bot.message_handler(commands=['give'])
def give_command(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Формат: /give [user_id] [сумма]")
        return
    uid = int(args[1])
    amount = int(args[2])
    db_query("UPDATE users SET balance = balance + ? WHERE id=?", (amount, uid))
    bot.reply_to(message, f"✅ Выдано {amount} 🪙 пользователю {uid}")
    try:
        bot.send_message(uid, f"🎁 Администратор выдал вам {amount} 🪙")
    except:
        pass

@bot.message_handler(commands=['createpromo'])
def create_promo_command(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(message, "Формат: /createpromo [код] [награда] [лимит]")
        return
    code = args[1].upper()
    reward = int(args[2])
    limit = int(args[3])
    db_query("INSERT OR IGNORE INTO promo VALUES (?,?,?,0)", (code, reward, limit))
    bot.reply_to(message, f"Промокод {code} создан (награда {reward}, лимит {limit})")

@bot.message_handler(commands=['ban'])
def ban_command(message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Формат: /ban [user_id]")
        return
    uid = int(args[1])
    db_query("DELETE FROM users WHERE id=?", (uid,))
    bot.reply_to(message, f"Пользователь {uid} забанен")

# ======================== ЗАПУСК СЕРВЕРА ========================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. v31.0 is running", 200

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