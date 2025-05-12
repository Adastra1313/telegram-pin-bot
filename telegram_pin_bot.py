import os
import json
import datetime
from flask import Flask
from dotenv import load_dotenv
from telegram import Bot, ReplyKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# 1) Завантажуємо .env
load_dotenv()
TOKEN             = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS      = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x.strip()]
STORAGE_CHAT_ID   = int(os.getenv("STORAGE_CHAT_ID","0"))
PINNED_MESSAGE_ID = int(os.getenv("PINNED_MESSAGE_ID","0"))

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID]):
    raise RuntimeError("Вкажіть у середовищі всі змінні: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID")

bot = Bot(token=TOKEN)
updater = Updater(bot=bot, use_context=True)
dp = updater.dispatcher

# Зберігаємо стан вибору категорії для кожного user_id
user_state: dict[int,str] = {}

def load_db() -> dict:
    msg = bot.get_chat(STORAGE_CHAT_ID).pinned_message
    try:
        return json.loads(msg.text or "{}")
    except:
        return {}

def save_db(db: dict):
    text = json.dumps(db, ensure_ascii=False, indent=2)
    bot.edit_message_text(
        chat_id=STORAGE_CHAT_ID,
        message_id=PINNED_MESSAGE_ID,
        text=text
    )

def start(update: Update, ctx: CallbackContext):
    kb = ReplyKeyboardMarkup(
        [["Контент з весілля, гендерпатія, освідчення"],
         ["Корпоративи, дні народження, конференції"]],
        resize_keyboard=True
    )
    update.message.reply_text(
        "Що за котик завітав? Що сьогодні назнімав?",
        reply_markup=kb
    )

def choose_category(update: Update, ctx: CallbackContext):
    text = update.message.text
    user_state[update.effective_user.id] = text
    update.message.reply_text("Надішліть, будь ласка, посилання на сторіс.")

def receive_link(update: Update, ctx: CallbackContext):
    link = update.message.text
    uid = str(update.effective_user.id)
    db = load_db()
    entry = db.get(uid, {"name": update.effective_user.full_name, "count":0, "subs":[]})
    entry["count"] += 1
    entry["subs"].append({
        "category": user_state.get(update.effective_user.id,""),
        "link":     link,
        "time":     datetime.datetime.utcnow().isoformat()
    })
    db[uid] = entry
    save_db(db)

    update.message.reply_text(f"Контент отримано! Твій лічильник чемпіона: {entry['count']}")

    alert = (
        f"🆕 Новий контент від {entry['name']}\n"
        f"Категорія: {user_state.get(update.effective_user.id)}\n"
        f"Лінк: {link}"
    )
    for cid in SMM_CHAT_IDS:
        bot.send_message(chat_id=cid, text=alert)

# Реєструємо хендлери
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.regex(r"^(Контент з весілля, гендерпатія, освідчення|Корпоративи, дні народження, конференції)$"), choose_category))
dp.add_handler(MessageHandler(Filters.regex(r"^http"), receive_link))

# --- Keep-alive через Flask ---
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running"
def run_web():
    app.run(host="0.0.0.0", port=3000)

if __name__ == "__main__":
    # Запускаємо Flask у паралельному потоці, щоб бот не спав
    import threading
    threading.Thread(target=run_web).start()
    # І запускаємо Telegram-полінг
    updater.start_polling(drop_pending_updates=True)
    updater.idle()
