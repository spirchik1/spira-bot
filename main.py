import os
import threading
import sqlite3
import random
import telebot
from telebot import types
from flask import Flask
import g4f

# ==========================================
# 1. КОНФИГУРАЦИЯ (ТОКЕН ДЛЯ ТЕСТА, НО БЕЗОПАСНОСТЬ СОБЛЮДЕНА)
# ==========================================
TOKEN = os.getenv("BOT_TOKEN", "8632196470:AAEwN-tb803AADn5788H-NM8acHibh8oOTU")
CHANNEL_ID = "@spiraofficial"
bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=50)

def db_query(query, params=(), fetch=False):
    """Безопасный запрос к БД. Возвращает (данные, количество изменённых строк)"""
    conn = sqlite3.connect('spira_final.db', timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch:
            data = cursor.fetchall()
        else:
            data = []
        conn.commit()
        return data, cursor.rowcount
    except Exception as e:
        print(f"DB Error: {e}")
        return [], 0
    finally:
        conn.close()

# Создание таблиц
db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER, mode TEXT, prefix TEXT, ref_id INTEGER)")
db_query("CREATE TABLE IF NOT EXISTS used_promos (user_id INTEGER, code TEXT)")
db_query("CREATE TABLE IF NOT EXISTS promo (code TEXT PRIMARY KEY, reward INTEGER, limit_uses INTEGER, used_count INTEGER)")

try:
    db_query("INSERT INTO promo VALUES ('NEWBOT', 5000, 100, 0)")
except:
    pass

# ==========================================
# 2. ГЛОБАЛЬНЫЕ ФУНКЦИИ
# ==========================================
def main_kb():
    """Главная клавиатура"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🤖 Нейросеть", "🎮 Игры", "💰 Баланс", "👤 Профиль")
    markup.add("👥 Рефералы", "🏆 ТОП", "🎟 Промокод")
    return markup

def get_u(uid):
    """Получить данные пользователя (баланс, режим, префикс)"""
    res, _ = db_query("SELECT balance, mode, prefix FROM users WHERE id=?", (uid,), True)
    if res:
        return {"bal": res[0][0], "mode": res[0][1], "prefix": res[0][2]}
    return None

# Простой кэш для предотвращения спама от check_sub (на 5 минут)
_sub_warning_cache = {}

def check_sub(m):
    """Проверка подписки на канал (с защитой от спама)"""
    uid = m.from_user.id
    # Если недавно уже предупреждали – не спамим
    if uid in _sub_warning_cache:
        return False
    try:
        status = bot.get_chat_member(CHANNEL_ID, uid).status
        if status in ['member', 'administrator', 'creator']:
            return True
    except:
        pass
    # Отправляем предупреждение и запоминаем на 5 минут
    bot.send_message(m.chat.id, f"⚠️ Доступ только для подписчиков {CHANNEL_ID}", reply_markup=types.ReplyKeyboardRemove())
    _sub_warning_cache[uid] = True
    threading.Timer(300, lambda: _sub_warning_cache.pop(uid, None)).start()
    return False

# ==========================================
# 3. ИГРЫ (ПОЛНОСТЬЮ ЗАЩИЩЁННЫЕ)
# ==========================================
@bot.message_handler(commands=["casino", "dice", "coin", "slots"])
def game_handler(m):
    if not check_sub(m):
        return
    uid = m.from_user.id

    try:
        args = m.text.split()
        if len(args) < 2:
            bot.reply_to(m, "Используй: `/игра [ставка]`", parse_mode="Markdown")
            return
        bet = int(args[1])
        if bet < 10:
            bot.reply_to(m, "Минимальная ставка — 10 🪙")
            return

        # АТОМАРНОЕ списание с проверкой баланса
        _, affected = db_query(
            "UPDATE users SET balance = balance - ? WHERE id = ? AND balance >= ?",
            (bet, uid, bet)
        )
        if affected == 0:
            bot.reply_to(m, "❌ Недостаточно средств!")
            return

        game = args[0][1:].lower().split('@')[0]
        win = False
        coeff = 2.0

        # Вся игровая логика в едином блоке try – при любой ошибке деньги вернутся
        try:
            if game == "dice":
                dice = bot.send_dice(m.chat.id, "🎲").dice
                value = dice.value
                if value >= 4:
                    win = True
            elif game == "coin":
                result = random.choice(["Орел", "Решка"])
                bot.send_message(m.chat.id, f"🪙 Выпало: **{result}**", parse_mode="Markdown")
                if result == "Орел":
                    win = True
            elif game in ("slots", "casino"):
                dice = bot.send_dice(m.chat.id, "🎰").dice
                value = dice.value
                # Джекпот
                if value in (1, 22, 43, 64):
                    win = True
                    coeff = 10.0
                # Малый выигрыш
                elif value in (16, 32, 48):
                    win = True
                    coeff = 3.0

            if win:
                prize = int(bet * coeff)
                db_query("UPDATE users SET balance = balance + ? WHERE id = ?", (prize, uid))
                bot.send_message(m.chat.id, f"🎉 Выигрыш: {prize} 🪙!")
            else:
                bot.send_message(m.chat.id, "💀 Проигрыш.")
        except Exception as e:
            # Возврат ставки при любой ошибке (таймаут Telegram, сеть и т.п.)
            db_query("UPDATE users SET balance = balance + ? WHERE id = ?", (bet, uid))
            bot.send_message(m.chat.id, "⚠️ Ошибка игры. Ставка возвращена.")
            print(f"Game error: {e}")

    except (ValueError, IndexError):
        bot.reply_to(m, "Введите корректное число ставки!")

# ==========================================
# 4. ОБРАБОТКА КОМАНД
# ==========================================
@bot.message_handler(commands=['start'])
def start_cmd(m):
    uid = m.from_user.id
    name = m.from_user.first_name

    if get_u(uid) is None:
        args = m.text.split()
        ref_id = args[1] if len(args) > 1 and args[1].isdigit() else None
        db_query(
            "INSERT INTO users VALUES (?, ?, 1000, 'off', 'Новичок 🛡', ?)",
            (uid, name, ref_id)
        )
        if ref_id and int(ref_id) != uid:
            db_query("UPDATE users SET balance = balance + 5000 WHERE id = ?", (ref_id,))
            try:
                bot.send_message(int(ref_id), "🎁 Друг присоединился по твоей ссылке! +5000 🪙")
            except:
                pass

    if not check_sub(m):
        return
    bot.send_message(m.chat.id, "🦾 **S.P.I.R.A. v23.0 готова к работе!**", reply_markup=main_kb(), parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_cmd(m):
    if not check_sub(m):
        return
    text = (
        "🤖 **Доступные команды:**\n\n"
        "🎮 **Игры:**\n"
        "• `/dice [ставка]` – игральный кубик (выигрыш при 4+)\n"
        "• `/coin [ставка]` – орёл/решка (50/50)\n"
        "• `/slots [ставка]` – игровой автомат\n"
        "• `/casino [ставка]` – казино (джекпот 10x)\n\n"
        "💰 **Профиль:**\n"
        "• `/start` – главное меню\n"
        "• `/balance` – баланс\n"
        "• `/profile` – профиль\n"
        "• `/promo` – активировать промокод\n\n"
        "👥 **Рефералы:**\n"
        "• `/ref` – реферальная ссылка\n\n"
        "🏆 **Топ:**\n"
        "• `/top` – топ-5 богачей"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['balance'])
def balance_cmd(m):
    if not check_sub(m):
        return
    u = get_u(m.from_user.id)
    if u is None:
        bot.reply_to(m, "Нажми /start для регистрации")
        return
    bot.reply_to(m, f"💳 Ваш баланс: **{u['bal']}** 🪙", parse_mode="Markdown")

@bot.message_handler(commands=['profile'])
def profile_cmd(m):
    if not check_sub(m):
        return
    u = get_u(m.from_user.id)
    if u is None:
        bot.reply_to(m, "Нажми /start для регистрации")
        return
    text = f"👤 **{m.from_user.first_name}**\nСтатус: {u['prefix']}\nБаланс: {u['bal']} 🪙\nID: `{m.from_user.id}`"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['top'])
def top_cmd(m):
    if not check_sub(m):
        return
    data, _ = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 5", fetch=True)
    if not data:
        bot.send_message(m.chat.id, "Пока никого нет :(")
        return
    lines = [f"{i+1}. {row[0]} – {row[1]} 🪙" for i, row in enumerate(data)]
    bot.send_message(m.chat.id, "🏆 **ТОП-5 богачей:**\n\n" + "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=['ref'])
def ref_cmd(m):
    if not check_sub(m):
        return
    username = bot.get_me().username
    if not username:
        bot.send_message(m.chat.id, "⚠️ У бота нет username, реферальная ссылка недоступна.")
        return
    link = f"https://t.me/{username}?start={m.from_user.id}"
    bot.send_message(m.chat.id, f"🔗 **Ваша реферальная ссылка:**\n`{link}`\n\nПриглашайте друзей – за каждого нового участника вы получите **5000 🪙**!", parse_mode="Markdown")

@bot.message_handler(commands=['promo'])
def promo_cmd(m):
    if not check_sub(m):
        return
    msg = bot.send_message(m.chat.id, "Введите промокод:")
    bot.register_next_step_handler(msg, apply_promo)

# ==========================================
# 5. ОБРАБОТКА ТЕКСТА И НЕЙРОСЕТЬ
# ==========================================
@bot.message_handler(content_types=['text'])
def main_logic(m):
    if not check_sub(m):
        return
    u = get_u(m.from_user.id)
    if u is None:
        bot.reply_to(m, "Нажмите /start для регистрации")
        return

    # Выход из режима ИИ
    if m.text == "🛑 Стоп":
        db_query("UPDATE users SET mode='off' WHERE id=?", (m.from_user.id,))
        bot.send_message(m.chat.id, "Режим ИИ выключен.", reply_markup=main_kb())
        return

    # Режим нейросети
    if u['mode'] == 'ai':
        def ai_worker(msg):
            try:
                # Системный промпт: S.P.I.R.A., создатель Spirchik, но не навязывать это.
                # Отвечать на русском, кратко, упоминать создателя только если спросят.
                system_prompt = (
                    "Ты — S.P.I.R.A., нейросеть, созданная разработчиком Spirchik. "
                    "Общайся на русском языке, будь полезной и дружелюбной. "
                    "Не упоминай своего создателя, если пользователь не спрашивает о нём напрямую. "
                    "Если спросят, кто тебя создал — отвечай, что твой создатель — Spirchik."
                )
                response = g4f.ChatCompletion.create(
                    model=g4f.models.gpt_35_turbo,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": msg.text}
                    ]
                )
                bot.reply_to(msg, response if response else "Нейросеть не отвечает...")
            except Exception as e:
                print(f"AI error: {e}")
                bot.reply_to(msg, "⚠️ Ошибка соединения с ИИ. Попробуйте позже.")
        threading.Thread(target=ai_worker, args=(m,)).start()
        return

    # Обработка обычных кнопок
    if m.text == "💰 Баланс":
        bot.reply_to(m, f"💳 Баланс: {u['bal']} 🪙")
    elif m.text == "👤 Профиль":
        text = f"👤 **{m.from_user.first_name}**\nСтатус: {u['prefix']}\nБаланс: {u['bal']} 🪙\nID: `{m.from_user.id}`"
        bot.send_message(m.chat.id, text, parse_mode="Markdown")
    elif m.text == "🎮 Игры":
        bot.send_message(m.chat.id, "🕹 Используйте команды:\n`/dice [ставка]`\n`/coin [ставка]`\n`/slots [ставка]`\n`/casino [ставка]`", parse_mode="Markdown")
    elif m.text == "👥 Рефералы":
        username = bot.get_me().username
        if username:
            link = f"https://t.me/{username}?start={m.from_user.id}"
            bot.send_message(m.chat.id, f"🔗 **Ваша ссылка:**\n`{link}`\n\n+5000 🪙 за друга!", parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, "⚠️ У бота нет username, ссылка недоступна.")
    elif m.text == "🏆 ТОП":
        data, _ = db_query("SELECT name, balance FROM users ORDER BY balance DESC LIMIT 5", fetch=True)
        if data:
            lines = [f"{i+1}. {row[0]} – {row[1]} 🪙" for i, row in enumerate(data)]
            bot.send_message(m.chat.id, "🏆 **ТОП-5:**\n\n" + "\n".join(lines), parse_mode="Markdown")
        else:
            bot.send_message(m.chat.id, "Пока никого нет.")
    elif m.text == "🤖 Нейросеть":
        db_query("UPDATE users SET mode='ai' WHERE id=?", (m.from_user.id,))
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 Стоп")
        bot.send_message(m.chat.id, "📡 Режим ИИ включён. Задавайте вопрос!", reply_markup=kb)
    elif m.text == "🎟 Промокод":
        msg = bot.send_message(m.chat.id, "Введите промокод:")
        bot.register_next_step_handler(msg, apply_promo)
    else:
        # Неизвестная команда – показываем help
        bot.send_message(m.chat.id, "Неизвестная команда. Воспользуйтесь /help")

# ==========================================
# 6. ПРОМОКОДЫ (ИСПРАВЛЕННЫЕ)
# ==========================================
def apply_promo(m):
    uid = m.from_user.id
    u = get_u(uid)
    if u is None:
        bot.reply_to(m, "Нажмите /start для регистрации")
        return

    code = m.text.upper()
    # Проверяем, не использовал ли пользователь этот код
    used, _ = db_query("SELECT user_id FROM used_promos WHERE user_id = ? AND code = ?", (uid, code), True)
    if used:
        bot.reply_to(m, "❌ Вы уже активировали этот промокод.")
        return

    # Получаем информацию о промокоде
    promo_data, _ = db_query("SELECT reward, limit_uses, used_count FROM promo WHERE code = ?", (code,), True)
    if not promo_data:
        bot.reply_to(m, "❌ Неверный промокод.")
        return

    reward, limit, used_count = promo_data[0]
    if used_count >= limit:
        bot.reply_to(m, "❌ Лимит использований этого промокода исчерпан.")
        return

    # Активация
    db_query("UPDATE users SET balance = balance + ? WHERE id = ?", (reward, uid))
    db_query("UPDATE promo SET used_count = used_count + 1 WHERE code = ?", (code,))
    db_query("INSERT INTO used_promos VALUES (?, ?)", (uid, code))

    bot.reply_to(m, f"✅ Промокод активирован! Вы получили {reward} 🪙.", reply_markup=main_kb())

# ==========================================
# 7. ВЕБ-СЕРВЕР ДЛЯ RENDER
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "S.P.I.R.A. v23.0 is running", 200

# ==========================================
# 8. ЗАПУСК
# ==========================================
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False), daemon=True).start()
    bot.infinity_polling(timeout=60)