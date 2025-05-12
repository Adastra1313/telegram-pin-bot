import os
import json
import datetime
from flask import Flask
from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 1) Завантажуємо .env
load_dotenv()
TOKEN             = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS      = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x.strip()]
STORAGE_CHAT_ID   = int(os.getenv("STORAGE_CHAT_ID","0"))
PINNED_MESSAGE_ID = int(os.getenv("PINNED_MESSAGE_ID","0"))

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID]):
    raise RuntimeError(
        "Вкажіть у середовищі: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID"
    )

# 2) Ініціалізація Flask (keep-alive)
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot is running"

# 3) Асинхронна ініціалізація Telegram-бота
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = ReplyKeyboardMarkup(
        [["Контент з весілля, гендерпатія, освідчення"],
         ["Корпоративи, дні народження, конференції"]],
        resize_keyboard=True
    )
    await update.message.reply_text(
        "Що за котик завітав? Що сьогодні назнімав?",
        reply_markup=kb
    )

async def choose_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["category"] = update.message.text
    await update.message.reply_text("Надішліть, будь ласка, посилання на сторіс.")

async def receive_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    uid  = str(update.effective_user.id)

    # Завантажити JSON із запін-повідомлення
    bot = Bot(TOKEN)
    chat = await bot.get_chat(STORAGE_CHAT_ID)
    pinned = chat.pinned_message
    try:
        db = json.loads(pinned.text or "{}")
    except:
        db = {}

    entry = db.get(uid, {"name": update.effective_user.full_name, "count": 0, "subs": []})
    entry["count"] += 1
    entry["subs"].append({
        "category": ctx.user_data.get("category", ""),
        "link":     link,
        "time":     datetime.datetime.utcnow().isoformat()
    })
    db[uid] = entry

    # Зберегти JSON назад
    text = json.dumps(db, ensure_ascii=False, indent=2)
    await bot.edit_message_text(
        chat_id=STORAGE_CHAT_ID,
        message_id=PINNED_MESSAGE_ID,
        text=text
    )

    # Відповісти користувачу
    await update.message.reply_text(f"Контент отримано! Твій лічильник чемпіона: {entry['count']}")

    # Сповістити SMM-чати
    alert = (
        f"🆕 Новий контент від {entry['name']}\n"
        f"Категорія: {ctx.user_data.get('category')}\n"
        f"Лінк: {link}"
    )
    for cid in SMM_CHAT_IDS:
        await bot.send_message(chat_id=cid, text=alert)

# 4) Побудова та запуск Application
if __name__ == "__main__":
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(Контент з весілля, гендерпатія, освідчення|Корпоративи, дні народження, конференції)$"
            ), choose_category
        )
    )
    application.add_handler(
        MessageHandler(filters.Regex(r"^http"), receive_link)
    )

    # Паралельно запускаємо Flask та полінг
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=3000)).start()
    application.run_polling()
