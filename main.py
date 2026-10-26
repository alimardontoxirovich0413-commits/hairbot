# Soch uslubini sinab ko'rish boti — server (Render/Docker) versiyasi
# Kalitlar KODDA EMAS, server sozlamalaridagi muhit o'zgaruvchilarida saqlanadi:
#   BOT_TOKEN       — BotFather bergan token
#   GEMINI_API_KEY  — AI Studio bergan kalit
#   MODEL           — (ixtiyoriy) rasm modeli nomi

import asyncio
import io
import os

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (BufferedInputFile, CallbackQuery,
                           InlineKeyboardButton, InlineKeyboardMarkup, Message)
from google import genai
from google.genai import types

BOT_TOKEN = os.environ["BOT_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = os.getenv("MODEL", "gemini-3.1-flash-image")

STYLES = {
    "quiff": ("Teksturali quiff",
              "a short textured quiff: faded short sides, top 5-7 cm styled up and slightly back"),
    "sidepart": ("Side part + fade",
                 "a classic side part with a low fade: short tapered sides, neat part, some volume on top"),
    "pompadour": ("Qisqa pompadour",
                  "a short pompadour: short sides, top combed back with height at the front"),
    "crop": ("French crop",
             "a textured French crop with a short fringe and a skin fade"),
}

client = genai.Client(api_key=GEMINI_API_KEY)
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
user_photos: dict[int, bytes] = {}  # faqat operativ xotirada saqlanadi


def kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=n, callback_data=f"style:{k}")]
        for k, (n, _) in STYLES.items()])


def generate(image: bytes, prompt: str) -> bytes | None:
    resp = client.models.generate_content(
        model=MODEL,
        contents=[types.Part.from_bytes(data=image, mime_type="image/jpeg"), prompt])
    for part in resp.candidates[0].content.parts:
        if part.inline_data:
            return part.inline_data.data
    return None


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Salom! 👋 Yuzingiz aniq ko'ringan selfi yuboring.\n"
                   "/ochir — rasmingizni o'chirish")


@dp.message(Command("ochir"))
async def ochir(m: Message):
    user_photos.pop(m.from_user.id, None)
    await m.answer("Rasmingiz o'chirildi ✅")


@dp.message(F.photo)
async def photo(m: Message):
    f = await bot.get_file(m.photo[-1].file_id)
    buf = io.BytesIO()
    await bot.download_file(f.file_path, buf)
    user_photos[m.from_user.id] = buf.getvalue()
    await m.answer("Uslubni tanlang:", reply_markup=kb())


@dp.callback_query(F.data.startswith("style:"))
async def style(c: CallbackQuery):
    key = c.data.split(":", 1)[1]
    img = user_photos.get(c.from_user.id)
    if img is None:
        await c.answer("Avval selfi yuboring", show_alert=True)
        return
    await c.answer()
    name, desc = STYLES[key]
    await c.message.answer(f"⏳ «{name}» tayyorlanmoqda...")
    prompt = (f"Edit this photo: change ONLY the person's hairstyle to {desc}. "
              "Keep the face, identity, skin, expression, clothing, background and "
              "lighting exactly the same. Photorealistic result.")
    try:
        result = await asyncio.to_thread(generate, img, prompt)
    except Exception as e:
        await c.message.answer(f"Xatolik: {e}")
        return
    if result is None:
        await c.message.answer("AI rasm qaytarmadi, boshqa selfi bilan urinib ko'ring.")
        return
    await c.message.answer_photo(BufferedInputFile(result, "natija.png"),
                                 caption=name, reply_markup=kb())


# Render bepul "Web Service" port ochilishini talab qiladi — shu uchun kichik veb-sahifa
async def health(_request):
    return web.Response(text="Bot ishlayapti")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000"))).start()


async def main():
    await run_web()
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
