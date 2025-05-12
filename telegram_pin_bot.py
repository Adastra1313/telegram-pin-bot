import os
import json
import datetime
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types

# --- Налаштування ---
load_dotenv()
TOKEN           = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS    = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x]
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID","0"))
DB_FILE         = "data.json"

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID]):
    raise RuntimeError("Вкажіть у .env: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID")

bot = Bot(token=TOKEN)
dp  = Dispatcher()

# --- Робота з локальною БД ---
def load_db() -> dict:
    if os.path.exists(DB_FILE):
        return json.load(open(DB_FILE, encoding="utf-8"))
    return {}

def save_db(db: dict):
    json.dump(db, open(DB_FILE,"w",encoding="utf-8"),
              ensure_ascii=False, indent=2)

# --- Обробники ---
@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Весільний контент","Корпоративний контент")
    await m.answer("Що за котик завітав? Що сьогодні назнімав?", reply_markup=kb)

@dp.message_handler(commands=["stats"])
async def cmd_stats(m: types.Message):
    db = load_db()
    uid = str(m.from_user.id)
    if uid in db:
        e = db[uid]
        text = f"📊 {e['name']}, ви надіслали {e['count']} лінків\n\n🏆 Топ-5:\n"
        top = sorted(db.values(), key=lambda x: x["count"], reverse=True)[:5]
        for i,u in enumerate(top,1):
            text += f"{i}. {u['name']} – {u['count']}\n"
    else:
        text = "Ви ще нічого не надсилали."
    await m.answer(text)

@dp.message_handler(lambda m: m.text in ["Весільний контент","Корпоративний контент"])
async def choose(m: types.Message):
    # Запам’ятовуємо категорію
    dp.storage.data[m.from_user.id] = {"cat": m.text}
    await m.answer("Надішліть лінк (http…)")

@dp.message_handler(lambda m: m.text and m.text.startswith("http"))
async def receive(m: types.Message):
    db = load_db()
    uid   = str(m.from_user.id)
    entry = db.get(uid, {"name":m.from_user.full_name, "count":0})
    entry["count"] += 1
    db[uid] = entry
    save_db(db)

    # Публікація в Storage-канал
    await bot.send_message(
        STORAGE_CHAT_ID,
        f"#{entry['count']} | {entry['name']} | {m.text}"
    )
    # Відповідь
    await m.answer("Дуже крутий контент, я тебе обожнюю! Чекаю наступного.")
    # Сповіщення SMM
    note = f"🆕 {entry['name']} (#{entry['count']})\n{m.text}"
    for cid in SMM_CHAT_IDS:
        await bot.send_message(cid, note)

# --- Стартуємо polling через asyncio ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, skip_updates=True))
