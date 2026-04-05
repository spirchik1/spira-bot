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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ======================== КОНФИГУРАЦИЯ ========================
TOKEN = "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU"          # Токен бота
ADMIN_ID = 6133141754                                            # Ваш Telegram ID (администратор бота)
CHANNEL_ID = "@spiraofficial"                                    # Канал для обязательной подписки (можно изменить)

bot = telebot.TeleBot(TOKEN, threaded=True)

# ======================== БАЗА ДАННЫХ ========================
def db_query(query, params=(), fetch=False):
    """Универсальная функция для работы с SQLite"""
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

# Создание всех таблиц (структура базы данных)
db_query("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    balance INTEGER,
    mode TEXT,
    prefix TEXT,                 -- текущий активный префикс (звание)
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
    game_tic_tac_toe_wins INTEGER DEFAULT 0,
    game_mines_wins INTEGER DEFAULT 0
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

# ======================== НАЧАЛЬНОЕ ЗАПОЛНЕНИЕ ТАБЛИЦ ========================
# Магазин префиксов (20+ званий)
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

# Кейсы
db_query("INSERT OR IGNORE INTO cases VALUES ('case1','Обычный кейс',5000,'[{\"item\":\"prefix_winner\",\"prob\":0.3},{\"item\":\"boost1\",\"prob\":0.7}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case2','Редкий кейс',15000,'[{\"item\":\"prefix_legend\",\"prob\":0.2},{\"item\":\"prefix_king\",\"prob\":0.3},{\"item\":\"skin_gold\",\"prob\":0.5}]')")
db_query("INSERT OR IGNORE INTO cases VALUES ('case3','Легендарный кейс',50000,'[{\"item\":\"prefix_god\",\"prob\":0.1},{\"item\":\"prefix_dragon\",\"prob\":0.2},{\"item\":\"prefix_immortal\",\"prob\":0.7}]')")

# Задания (7 штук)
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

# Промокод по умолчанию
db_query("INSERT OR IGNORE INTO promo VALUES ('MEGA2024', 10000, 50, 0)")

logger.info("База данных инициализирована")

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def get_user(uid):
    """Получить данные пользователя (баланс, текущий префикс и т.д.)"""
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
    """Вернуть отображаемый префикс для пользователя (в личке или группе)"""
    user = get_user(uid)
    if user:
        return user['prefix']
    return "Новичок 🛡"

def is_group_admin(chat_id, user_id):
    """Проверить, является ли пользователь администратором группы (для выдачи звания [Админ])"""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def update_stats(uid, game, win, bet=0):
    """Обновить статистику, опыт, уровни, квесты"""
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
        stats = [(0, 0, 0, 0, 0, 0, 0, 0)]

    total_games = (stats[0][1] or 0) + 1
    total_wins = (stats[0][2] or 0) + (1 if win else 0)
    # Обновляем конкретную игру
    game_cols = {
        'dice': 'game_dice_wins',
        'coin': 'game_coin_wins',
        'slots': 'game_slots_wins',
        'casino': 'game_casino_wins',
        'ttt': 'game_tic_tac_toe_wins',
        'mines': 'game_mines_wins'
    }
    col = game_cols.get(game, 'game_dice_wins')
    db_query(f"UPDATE stats SET total_games=?, total_wins=?, {col} = {col} + ? WHERE user_id=?", (total_games, total_wins, 1 if win else 0, uid))

    # Квесты
    if win:
        db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='win_games') AND completed=0", (uid,))
    db_query("UPDATE user_quests SET progress = progress + 1 WHERE user_id=? AND quest_id IN (SELECT id FROM quests WHERE goal_type='play_games') AND completed=0", (uid,))

    # Проверка выполнения квестов
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
    """Проверка подписки на канал (если нужно) – для личных сообщений"""
    # Для групп эта проверка не нужна, поэтому пропускаем
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
    """Главная клавиатура (для личных сообщений)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод", "📦 Кейсы", "🛒 Магазин")
    markup.add("⚙️ Бонус", "🎲 Статистика", "🏅 Инвентарь", "🎤 TTS", "🎨 Imagine")
    markup.add("🏟 Турнир", "⚔️ Аукцион", "📜 Задания", "🏛 Гильдия", "➕ Добавить бота в чат")
    return markup

# ======================== ИГРЫ ========================
@bot.message_handler(func=lambda m: m.text == "🎮 Игры")
def games_menu(message):
    games = ["dice", "coin", "slots", "casino", "ttt", "mines"]
    markup = types.InlineKeyboardMarkup(row_width=2)
    for g in games:
        markup.add(types.InlineKeyboardButton(g.capitalize(), callback_data=f"game_{g}"))
    bot.send_message(message.chat.id, "🎲 Выберите игру:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def game_callback(call):
    game = call.data.split("_")[1]
    if game == "ttt":
        # Для крестиков-ноликов сначала спросим ставку
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bet in [100, 500, 1000, 5000]:
            markup.add(types.InlineKeyboardButton(f"{bet} 🪙", callback_data=f"ttt_bet_{bet}"))
        bot.edit_message_text("Выберите ставку для игры в крестики-нолики:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif game == "mines":
        # Для мин – сначала количество мин
        markup = types.InlineKeyboardMarkup(row_width=5)
        for mines in range(1, 11):
            markup.add(types.InlineKeyboardButton(str(mines), callback_data=f"mines_mines_{mines}"))
        bot.edit_message_text("Сколько мин будет на поле? (1-10):", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else:
        # dice, coin, slots, casino
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
    bot.answer_callback_query(call.id)

# -------------------- Крестики-нолики (TTT) --------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("ttt_bet_"))
def ttt_bet_callback(call):
    bet = int(call.data.split("_")[2])
    uid = call.from_user.id
    user = get_user(uid)
    if not user or user['bal'] < bet:
        bot.answer_callback_query(call.id, "Недостаточно монет")
        return
    bot.send_message(call.message.chat.id, "Введите Telegram ID или username противника. Или напишите 'бот' для игры с ботом.")
    bot.register_next_step_handler(call.message, lambda m: ttt_opponent(m, bet, uid))

def ttt_opponent(message, bet, uid):
    text = message.text.strip()
    if text.lower() == "бот":
        start_ttt_game(message.chat.id, uid, None, bet)
    else:
        # Поиск противника
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
            bot.send_message(message.chat.id, "Противник не зарегистрирован в боте.")
            return
        if opp_user['bal'] < bet:
            bot.send_message(message.chat.id, "У противника недостаточно монет.")
            return
        start_ttt_game(message.chat.id, uid, opponent, bet)

def start_ttt_game(chat_id, player1, player2, bet):
    board = [" "] * 9
    turn = 1  # 1 - X (игрок1), 2 - O (игрок2 или бот)
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
    for i in range(0, 9, 3):
        row = board[i:i+3]
        text += " | ".join([c if c != " " else str(i+1) for c in row]) + "\n" + ("---------\n" if i < 6 else "")
    markup = types.InlineKeyboardMarkup(row_width=3)
    for i in range(9):
        if board[i] == " ":
            markup.add(types.InlineKeyboardButton(str(i+1), callback_data=f"ttt_move_{game_id}_{i}"))
    bot.send_message(chat_id, text, reply_markup=markup)

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
    if (turn == 1 and uid != p1) or (turn == 2 and p2 and uid != p2):
        bot.answer_callback_query(call.id, "Сейчас не ваш ход")
        return
    if p2 is None and turn == 2:
        # Ход бота
        bot.answer_callback_query(call.id, "Сейчас ходит бот")
        return
    if board[pos] != " ":
        bot.answer_callback_query(call.id, "Клетка занята")
        return
    # Делаем ход
    board[pos] = "X" if turn == 1 else "O"
    winner = check_ttt_winner(board)
    if winner:
        # Есть победитель
        winner_id = p1 if winner == "X" else p2
        if winner_id:
            prize = int(bet * 1.8)
            db_query("UPDATE users SET balance = balance + ? WHERE id=?", (prize, winner_id))
            bot.send_message(call.message.chat.id, f"🏆 Игрок {winner_id} выиграл {prize} 🪙!")
            update_stats(winner_id, "ttt", True, bet)
            if p2 and p2 != winner_id:
                update_stats(p2, "ttt", False, bet)
            else:
                update_stats(p1, "ttt", False, bet)
        else:
            # победа бота
            prize = int(bet * 1.8)
            db_query("UPDATE users S