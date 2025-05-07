import asyncio
import logging
from collections import defaultdict
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import (
    Message, InputMediaPhoto,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.client.default import DefaultBotProperties

API_TOKEN = '8157495833:AAEe3kl34YIZ0hE2YancGubq-kJ5OdymlLQ'
ADMINS = [6705001934]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
user_data = {}
user_locks = defaultdict(asyncio.Lock)

async def clear_messages(uid, message_ids):
    for mid in message_ids:
        try:
            await bot.delete_message(uid, mid)
        except:
            continue

@dp.message(CommandStart())
@dp.message(F.text == "➕ Отправить ещё одну группу")
async def start(message: Message):
    uid = message.from_user.id
    async with user_locks[uid]:
        user_data[uid] = {
            "stage": "choose_branch",
            "msg_ids_to_delete": []
        }
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏢 Ташкент"), KeyboardButton(text="🏢 Самарканд")],
                [KeyboardButton(text="🏢 Сайрам")]
            ],
            resize_keyboard=True
        )
        await message.answer("Выберите филиал:", reply_markup=kb)

@dp.message(F.text.startswith("🏢"))
async def choose_branch(message: Message):
    uid = message.from_user.id
    async with user_locks[uid]:
        branch = message.text.replace("🏢 ", "")
        user_data[uid] = {
            "branch": branch,
            "stage": "choose_category",
            "msg_ids_to_delete": []
        }
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🩺 Лечение"), KeyboardButton(text="🎓 Обучение")]],
            resize_keyboard=True
        )
        await message.answer(f"Вы выбрали филиал: {branch}")
        await message.answer("Теперь выберите категорию:", reply_markup=kb)

@dp.message(F.text.in_(["🩺 Лечение", "🎓 Обучение"]))
async def choose_category(message: Message):
    uid = message.from_user.id
    async with user_locks[uid]:
        category = "лечение" if "Лечение" in message.text else "обучение"
        user_data[uid].update({
            "category": category,
            "stage": "collecting",
            "step": 0,
            "videos": [],
            "video_texts": [],
            "photos": [],
            "photo_texts": [],
            "photo_types": [],
            "msg_ids_to_delete": []
        })
        await message.answer(f"Вы выбрали категорию: {category}")
        sent = await message.answer("Отправьте 3 видео по очереди.", reply_markup=ReplyKeyboardRemove())
        user_data[uid]["msg_ids_to_delete"].append(sent.message_id)

@dp.message(F.video)
async def handle_video(message: Message):
    await process_video(message, message.video.file_id)

@dp.message(F.document)
async def handle_document(message: Message):
    uid = message.from_user.id
    mime = message.document.mime_type
    if mime.startswith("video/"):
        await process_video(message, message.document.file_id)
    elif mime.startswith("image/"):
        await process_photo(message, message.document.file_id, file_type="document")

async def process_video(message: Message, file_id: str):
    uid = message.from_user.id
    async with user_locks[uid]:
        data = user_data.get(uid)
        if not data or data["stage"] != "collecting":
            return
        step = data["step"]
        await clear_messages(uid, data["msg_ids_to_delete"])
        data["msg_ids_to_delete"].clear()
        if 0 <= step <= 2:
            data["videos"].append(file_id)
            data["step"] += 1
            if data["step"] == 3:
                sent = await message.answer("✅ Все 3 видео получены. Теперь отправьте 3 подписи к ним.")
            else:
                sent = await message.answer(f"✅ Видео {len(data['videos'])} получено. Отправьте следующее.")
            data["msg_ids_to_delete"].append(sent.message_id)
        else:
            sent = await message.answer("❌ Сейчас ожидается текст, а не видео.")
            data["msg_ids_to_delete"].append(sent.message_id)

@dp.message(F.text)
async def handle_text(message: Message):
    uid = message.from_user.id
    async with user_locks[uid]:
        data = user_data.get(uid)
        if not data or data["stage"] != "collecting":
            return
        step = data["step"]
        await clear_messages(uid, data["msg_ids_to_delete"])
        data["msg_ids_to_delete"].clear()
        if 3 <= step <= 5:
            data["video_texts"].append(message.text)
            data["step"] += 1
            if data["step"] == 6:
                sent = await message.answer("✅ Все подписи к видео получены. Теперь отправьте 3 фото.")
            else:
                sent = await message.answer(f"📝 Подпись {len(data['video_texts'])}/3 сохранена.")
            data["msg_ids_to_delete"].append(sent.message_id)
        elif step == 9:
            data["photo_texts"].append(message.text)
            data["step"] += 1
            sent = await message.answer("✅ Подпись к первым 3 фото получена. Теперь отправьте ещё 3 фото.")
            data["msg_ids_to_delete"].append(sent.message_id)
        elif step == 13:
            data["photo_texts"].append(message.text)
            data["step"] += 1
            await message.answer("📤 Отправляем всё администраторам...")
            await send_to_admins(uid, data)
            user_data.pop(uid, None)
        else:
            sent = await message.answer("❌ Сейчас текст не ожидается.")
            data["msg_ids_to_delete"].append(sent.message_id)

@dp.message(F.photo)
async def handle_photo(message: Message):
    await process_photo(message, message.photo[-1].file_id, file_type="photo")

async def process_photo(message: Message, file_id: str, file_type="photo"):
    uid = message.from_user.id
    async with user_locks[uid]:
        data = user_data.get(uid)
        if not data or data["stage"] != "collecting":
            return
        step = data["step"]
        await clear_messages(uid, data["msg_ids_to_delete"])
        data["msg_ids_to_delete"].clear()
        if 6 <= step <= 8 or 10 <= step <= 12:
            data["photos"].append(file_id)
            data["photo_types"].append(file_type)
            data["step"] += 1
            if data["step"] == 9:
                sent = await message.answer("🖼️ Получены 3 фото. Теперь отправьте подпись к ним.")
            elif data["step"] == 13:
                sent = await message.answer("🖼️ Получены ещё 3 фото. Теперь отправьте подпись ко второй группе.")
            else:
                sent = await message.answer(f"🖼️ Фото {len(data['photos'])}/6 принято.")
            data["msg_ids_to_delete"].append(sent.message_id)
        else:
            sent = await message.answer("❌ Сейчас фото не ожидаются.")
            data["msg_ids_to_delete"].append(sent.message_id)

async def send_to_admins(uid, data):
    header = f"📍 Филиал: {data['branch']}\n🧭 Категория: {data['category']}"
    for admin in ADMINS:
        await bot.send_message(admin, header)
        for i in range(3):
            await bot.send_video(admin, video=data["videos"][i], caption=data["video_texts"][i])
        for i in range(2):
            start = i * 3
            group = data["photos"][start:start+3]
            if all(t == "photo" for t in data["photo_types"][start:start+3]):
                media_group = [InputMediaPhoto(media=g) for g in group]
                await bot.send_media_group(admin, media=media_group)
            else:
                for file_id in group:
                    await bot.send_document(admin, document=file_id)
            await bot.send_message(admin, f"📝 Подпись к фото: {data['photo_texts'][i]}")
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➕ Отправить ещё одну группу")]],
        resize_keyboard=True
    )
    await bot.send_message(uid, "✅ Всё успешно отправлено! Спасибо 🙏", reply_markup=kb)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
