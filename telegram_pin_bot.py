import os
import json
import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Завантажуємо змінні середовища з .env
load_dotenv()
TOKEN             = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS      = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x.strip()]
STORAGE_CHAT_ID   = int(os.getenv("STORAGE_CHAT_ID","0"))
PINNED_MESSAGE_ID = int(os.getenv("PINNED_MESSAGE_ID","0"))

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID]):
    raise RuntimeError("Потрібно встановити всі змінні середовища: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID, PINNED_MESSAGE_ID")

bot = Bot(token=TOKEN)
dp  = Dispatcher(bot)
user_state: dict[int, str] = {}

async def load_db() -> dict:
    chat   = await bot.get_chat(STORAGE_CHAT_ID)
    pinned = chat.pinned_message
    try:
        return json.loads(pinned.text or "{}")
    except:
        return {}

async def save_db(data: dict):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    await bot.edit_message_text(
        chat_id=STORAGE_CHAT_ID,
        message_id=PINNED_MESSAGE_ID,
        text=text
    )

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        "Контент з весілля, гендерпатія, освідчення",
        "Корпоративи, дні народження, конференції"
    )
    await message.answer("Що за котик завітав? Що сьогодні назнімав?", reply_markup=kb)

@dp.message_handler(lambda m: m.text in [
    "Контент з весілля, гендерпатія, освідчення",
    "Корпоративи, дні народження, конференції"
])
async def choose_category(message: types.Message):
    user_state[message.from_user.id] = message.text
    await message.answer("Надішліть, будь ласка, посилання на сторіс.")

@dp.message_handler(lambda m: m.text and m.text.startswith("http"))
async def receive_link(message: types.Message):
    db  = await load_db()
    uid = str(message.from_user.id)
    entry = db.get(uid, {"name": message.from_user.full_name, "count": 0, "subs": []})
    entry["count"] += 1
    entry["subs"].append({
        "category": user_state.get(message.from_user.id, ""),
        "link":     message.text,
        "time":     datetime.datetime.utcnow().isoformat()
    })
    db[uid] = entry
    await save_db(db)
    await message.answer(f"Контент отримано! Твій лічильник чемпіона: {entry['count']}")
    alert = (
        f"🆕 Новий контент від {entry['name']}\n"
        f"Категорія: {user_state.get(message.from_user.id)}\n"
        f"Лінк: {message.text}"
    )
    for cid in SMM_CHAT_IDS:
        await bot.send_message(chat_id=cid, text=alert)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
