import os, json, datetime, threading
from aiogram import Bot, Dispatcher, types
from flask import Flask
from dotenv import load_dotenv

# 1. Завантажуємо .env
load_dotenv()

# 2. Змінні середовища
TOKEN            = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS     = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x.strip()]
STORAGE_CHAT_ID  = int(os.getenv("STORAGE_CHAT_ID","0"))
PINNED_MESSAGE_ID= int(os.getenv("PINNED_MESSAGE_ID","0"))

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID]):
    raise RuntimeError("Встановіть всі змінні: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID")

bot = Bot(token=TOKEN)
dp  = Dispatcher(bot)
user_state = {}

async def load_db():
    chat   = await bot.get_chat(STORAGE_CHAT_ID)
    pinned = chat.pinned_message
    try:
        return json.loads(pinned.text or "{}")
    except:
        return {}

async def save_db(data):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    await bot.edit_message_text(
        chat_id=STORAGE_CHAT_ID,
        message_id=PINNED_MESSAGE_ID,
        text=text
    )

@dp.message_handler(commands=['start'])
async def cmd_start(msg: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
      "Контент з весілля, гендерпатія, освідчення",
      "Корпоративи, дні народження, конференції"
    )
    await msg.answer("Що за котик завітав? Що сьогодні назнімав?", reply_markup=kb)

@dp.message_handler(lambda m: m.text in [
    "Контент з весілля, гендерпатія, освідчення",
    "Корпоративи, дні народження, конференції"
])
async def choose_cat(msg: types.Message):
    user_state[msg.from_user.id] = msg.text
    await msg.answer("Надішліть, будь ласка, посилання на сторіс.")

@dp.message_handler(lambda m: m.text and m.text.startswith("http"))
async def receive_link(msg: types.Message):
    db  = await load_db()
    uid = str(msg.from_user.id)
    ent = db.get(uid, {"name":msg.from_user.full_name,"count":0,"subs":[]})
    ent["count"] += 1
    ent["subs"].append({
      "category": user_state.get(msg.from_user.id,""),
      "link":     msg.text,
      "time":     datetime.datetime.utcnow().isoformat()
    })
    db[uid] = ent
    await save_db(db)

    await msg.answer(f"Контент отримано! Твій лічильник чемпіона: {ent['count']}")
    alert = (
      f"🆕 Новий контент від {ent['name']}\n"
      f"Категорія: {user_state.get(msg.from_user.id)}\n"
      f"Лінк: {msg.text}"
    )
    for cid in SMM_CHAT_IDS:
        await bot.send_message(chat_id=cid, text=alert)

# — keep-alive через Flask —
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running"
def run_app(): app.run(host='0.0.0.0', port=3000)
threading.Thread(target=run_app).start()

if __name__=="__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
