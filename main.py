from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "S.P.I.R.A. в строю 24/7"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Запускаем "оживитель"
keep_alive()
import telebot
import g4f
from g4f.client import Client
import phonenumbers
from phonenumbers import carrier, geocoder

TOKEN = "8632196470:AAGvrAgQczmegYRJN1YOgoyT_tKiacazQ_A"

bot = telebot.TeleBot(TOKEN)
client = Client()

SYSTEM_PROMPT = """Ты — S.P.I.R.A., интеллектуальный ИИ-ассистент.

Правила поведения:
- С нормальными людьми ты вежлив, краток и по делу.
- Если тебя оскорбляют или оскорбляют твоего создателя — ставь наглеца на место жёстко и без церемоний.
- О своём создателе (spirchik) говори только если спросят напрямую. Тогда отвечай: "Меня создал spirchik."
- Ты не Google, не OpenAI. Ты S.P.I.R.A. Точка.
- Отвечай всегда на том языке, на котором пишет пользователь."""

osint_mode = {}


def ask_spira(text: str) -> str:
    response = client.chat.completions.create(
        model="openai",
        provider=g4f.Provider.PollinationsAI,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        timeout=30
    )
    return response.choices[0].message.content


@bot.message_handler(commands=["start", "help"])
def start(message):
    bot.reply_to(message,
        "🦾 S.P.I.R.A. в сети.\n\n"
        "Задавай вопросы — отвечу.\n"
        "[ OSINT: system_override_777 ]"
    )


@bot.message_handler(func=lambda m: True)
def handle(message):
    cid = message.chat.id
    text = message.text.strip()

    if text == "system_override_777":
        osint_mode[cid] = True
        bot.send_message(cid, "⚠️ ПРОТОКОЛ OSINT АКТИВИРОВАН.\nВведите номер телефона.")
        return

    if osint_mode.get(cid):
        try:
            n = phonenumbers.parse(text)
            region = geocoder.description_for_number(n, "ru") or "Неизвестно"
            op = carrier.name_for_number(n, "ru") or "Неизвестно"
            bot.send_message(cid,
                f"🎯 OSINT результат:\n"
                f"🌍 Регион: {region}\n"
                f"📶 Оператор: {op}"
            )
        except Exception:
            bot.send_message(cid, "❌ Не удалось разобрать номер. OSINT-режим выключен.")
            osint_mode[cid] = False
        return

    try:
        bot.send_chat_action(cid, "typing")
        reply = ask_spira(text)
        bot.reply_to(message, reply)
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        bot.reply_to(message, "⚠️ Временный сбой. Повтори через несколько секунд.")


print("S.P.I.R.A. запущена...")
bot.polling(none_stop=True)
