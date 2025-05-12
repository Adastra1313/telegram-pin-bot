import os
import json
import datetime
from threading import Thread

from flask import Flask
from dotenv import load_dotenv

from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# 1) Завантажуємо змінні середовища з .env
load_dotenv()
TOKEN             = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS      = [int(x) for x in os.getenv("SMM_CHAT_IDS", "").split(",") if x.strip()]
STORAGE_CHAT_ID   = int(os.getenv("STORAGE_CHAT_ID", "0"))
PINNED_MESSAGE_ID = int(os.getenv("PINNED_MESSAGE_ID", "0"))

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID]):
    raise RuntimeError(
        "Вкажіть у середовищі: TELEGRAM_TOKEN, SMM_CHAT_IDS, "
        "STORAGE_CHAT_ID, PINNED_MESSAGE_ID"
    )

# 2) Flask-keepalive (щоб Render не спав бот)
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot is running"

def start_flask():
    # виключаємо перезавантажувач, щоб не створювати два процеси
    app.run(host="0.0.0.0", port=3000, use_reloader=False)

# 3) Глобальний стан вибору категорії
user_state: dict[int, str] = {}

# 4) Обробники Telegram-подій
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    user_id = update.effective_user.id
    user_state[user_id] = update.message.text
    await update.message.reply_text("Надішліть, будь ласка, посилання на сторіс.")

async def receive_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link    = update.message.text
    category = user_state.get(user_id, "")

    bot = Bot(token=TOKEN)
    # Завантажуємо поточний JSON з запін-повідомлення
    chat   = await bot.get_chat(STORAGE_CHAT_ID)
    pinned = chat.pinned_message
    try:
        db = json.loads(pinned.text or "{}")
    except:
        db = {}

    entry = db.get(str(user_id), {
        "name": update.effective_user.full_name,
        "count": 0,
        "subs": []
    })
    entry["count"] += 1
    entry["subs"].append({
        "category": category,
        "link":     link,
        "time":     datetime.datetime.utcnow().isoformat()
    })
    db[str(user_id)] = entry

    # Зберігаємо оновлений JSON назад у запін-повідомлення
    text = json.dumps(db, ensure_ascii=False, indent=2)
    await bot.edit_message_text(
        chat_id=STORAGE_CHAT_ID,
        message_id=PINNED_MESSAGE_ID,
        text=text
    )

    # Підтвердження для користувача
    await update.message.reply_text(
        f"Контент отримано! Твій лічильник чемпіона: {entry['count']}"
    )

    # Сповіщення в SMM-чатах
    alert = (
        f"🆕 Новий контент від {entry['name']}\n"
        f"Категорія: {category}\n"
        f"Лінк: {link}"
    )
    for cid in SMM_CHAT_IDS:
        await bot.send_message(chat_id=cid, text=alert)

# 5) Налаштовуємо та запускаємо бот
if __name__ == "__main__":
    # 5.1) Запускаємо Flask у фоновому потоці
    Thread(target=start_flask, daemon=True).start()

    # 5.2) Будуємо Telegram-додаток та реєструємо хендлери
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(
        MessageHandler(
            filters.Regex(
                r"^(Контент з весілля, гендерпатія, освідчення|Корпоративи, дні народження, конференції)$"
            ),
            choose_category
        )
    )
    application.add_handler(
        MessageHandler(filters.Regex(r"^https?://"), receive_link)
    )

    # 5.3) Запускаємо polling
    application.run_polling(drop_pending_updates=True)
