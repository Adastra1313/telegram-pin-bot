import os
import json
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types

# 1) Завантажуємо .env
load_dotenv()
TOKEN           = os.getenv("TELEGRAM_TOKEN")
SMM_CHAT_IDS    = [int(x) for x in os.getenv("SMM_CHAT_IDS", "").split(",") if x]
STORAGE_CHAT_ID = int(os.getenv("STORAGE_CHAT_ID", "0"))
DB_FILE         = "data.json"

if not all([TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID]):
    raise RuntimeError("Вкажіть у .env: TELEGRAM_TOKEN, SMM_CHAT_IDS, STORAGE_CHAT_ID")

# 2) Ініціалізація бота і диспетчера
bot = Bot(token=TOKEN)
dp  = Dispatcher()

# 3) Локальна БД
def load_db() -> dict:
    if os.path.exists(DB_FILE):
        return json.load(open(DB_FILE, encoding="utf-8"))
    return {}

def save_db(db: dict):
    json.dump(db, open(DB_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

# 4) Хендлери
async def cmd_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Весільний контент", "Корпоративний контент")
    await message.answer(
        "Що за котик завітав? Що сьогодні назнімав?",
        reply_markup=kb
    )

async def cmd_stats(message: types.Message):
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

async def choose_category(message: types.Message):
    dp.storage.data[message.from_user.id] = {"cat": message.text}
    await message.answer("Надішліть, будь ласка, лінк, що починається з http…")

async def receive_link(message: types.Message):
    db = load_db()
    uid = str(message.from_user.id)
    entry = db.get(uid, {"name": message.from_user.full_name, "count": 0})
    entry["count"] += 1
    db[uid] = entry
    save_db(db)

    # 1) Публікація в Storage-канал
    await bot.send_message(
        chat_id=STORAGE_CHAT_ID,
        text=f"#{entry['count']} | {entry['name']} | {message.text}"
    )
    # 2) Підтвердження користувачу
    await message.answer("Дуже крутий контент, я тебе обожнюю! Чекаю наступного.")
    # 3) Сповіщення SMM
    note = f"🆕 Новий контент від {entry['name']} (#{entry['count']})\n{message.text}"
    for cid in SMM_CHAT_IDS:
        await bot.send_message(cid, note)

# 5) Реєструємо хендлери через лямбда-функції
dp.message.register(cmd_start,       lambda m: m.text == "/start")
dp.message.register(cmd_stats,       lambda m: m.text == "/stats")
dp.message.register(choose_category, lambda m: m.text in ["Весільний контент", "Корпоративний контент"])
dp.message.register(receive_link,    lambda m: m.text and m.text.startswith("http"))

# 6) Старт polling
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, skip_updates=True))
