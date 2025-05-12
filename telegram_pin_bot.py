import os
import json
import datetime
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup
from aiogram.filters import Command, Text

# --- Завантажуємо змінні середовища ---
load_dotenv()
TOKEN           = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS    = [int(x) for x in os.getenv("SMM_CHAT_IDS","").split(",") if x]
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID","0"))
DB_FILE         = "data.json"

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID]):
    raise RuntimeError("Потрібно вказати TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID в .env")

# --- Ініціалізація бота і диспетчера ---
bot = Bot(token=TOKEN)
dp  = Dispatcher()

# --- Функції роботи з локальною БД ---
def load_db() -> dict:
    if os.path.exists(DB_FILE):
        return json.load(open(DB_FILE, encoding="utf-8"))
    return {}

def save_db(db: dict):
    json.dump(db, open(DB_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

# --- Хендлери ---
async def cmd_start(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Весільний контент", "Корпоративний контент")
    await message.answer(
        "Що за котик завітав? Що сьогодні назнімав?",
        reply_markup=kb
    )

async def cmd_stats(message: Message):
    db = load_db()
    uid = str(message.from_user.id)
    if uid in db:
        e = db[uid]
        text = (
            f"📊 {e['name']}, ви надіслали {e['count']} лінків\n\n"
            "🏆 Топ-5 активних:\n"
        )
        top = sorted(db.values(), key=lambda x: x["count"], reverse=True)[:5]
        for i, u in enumerate(top, 1):
            text += f"{i}. {u['name']} – {u['count']}\n"
    else:
        text = "Ви ще нічого не надсилали."
    await message.answer(text)

async def choose_category(message: Message):
    # просто збережемо категорію в тимчасове сховище
    dp.storage.data[message.from_user.id] = {"cat": message.text}
    await message.answer("Надішліть, будь ласка, лінк (http…)")

async def receive_link(message: Message):
    db = load_db()
    uid = str(message.from_user.id)
    entry = db.get(uid, {"name": message.from_user.full_name, "count": 0})
    entry["count"] += 1
    db[uid] = entry
    save_db(db)

    # публікуємо в Storage-каналі
    await bot.send_message(
        chat_id=STORAGE_CHAT_ID,
        text=f"#{entry['count']} | {entry['name']} | {message.text}"
    )
    # відповідаємо користувачу
    await message.answer(
        "Дуже крутий контент, я тебе обожнюю! Чекаю наступного."
    )
    # сповіщаємо SMM-чати
    note = f"🆕 {entry['name']} (#{entry['count']})\n{message.text}"
    for cid in SMM_CHAT_IDS:
        await bot.send_message(cid, note)

# --- Реєструємо хендлери через новий API ---
dp.message.register(cmd_start, Command(commands=["start"]))
dp.message.register(cmd_stats, Command(commands=["stats"]))
dp.message.register(choose_category, Text(equals=["Весільний контент","Корпоративний контент"]))
dp.message.register(receive_link, lambda m: m.text and m.text.startswith("http"))

# --- Старт polling через asyncio ---
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, skip_updates=True))
