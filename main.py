import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy import create_engine, Column, Integer, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker

# settings
API_TOKEN = os.getenv("API_TOKEN")  # make sure this env var exists on server
DATABASE_URL = os.getenv("DATABASE_URL")

if not API_TOKEN:
    logging.critical("API_TOKEN is missing!")
    sys.exit(1)

# Проверка на наличие БД
if not DATABASE_URL:
    logging.critical("DATABASE_URL is missing!")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()


class UserMMR(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    current_mmr = Column(Integer, default=0)
    wins_today = Column(Integer, default=0)
    loss_today = Column(Integer, default=0)


engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# bot setup
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


async def handle_health_check(request):
    return web.Response(text="I am alive")


async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # render provides port via env var, default to 8080
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Web server started on port {port}")


def get_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ WIN (+25)")
    builder.button(text="❌ LOSE (-25)")
    builder.button(text="📊 Stats")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# db helper


def update_mmr(user_id, delta=0, set_value=None):
    session = Session()
    user = session.query(UserMMR).filter_by(user_id=user_id).first()

    if not user:
        # if user doesn't exist, init with provided value or default 3000
        start_val = set_value if set_value is not None else 3000
        user = UserMMR(user_id=user_id, current_mmr=start_val)
        session.add(user)

    if set_value is not None:
        # manual set via command
        user.current_mmr = set_value
        user.wins_today = 0
        user.loss_today = 0
    else:
        # standard update
        user.current_mmr += delta
        if delta > 0:
            user.wins_today += 1
        elif delta < 0:
            user.loss_today += 1

    new_mmr = user.current_mmr
    session.commit()
    session.close()
    return new_mmr

# handlers


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Sup, I'm tracking ur pts in dota. \n"
        "Use `/setmmr 4000` to set initial value.\n"
        "Press buttons or write numbers (e.g.: +30, -20).",
        reply_markup=get_keyboard(),
        parse_mode="Markdown"
    )


@dp.message(Command("setmmr"))
async def cmd_set_mmr(message: types.Message, command: CommandObject):
    if command.args is None:
        await message.answer("Usage: `/setmmr 4500`")
        return
    try:
        value = int(command.args)
        new_mmr = update_mmr(message.from_user.id, set_value=value)
        await message.answer(f"Got it. Start pts: **{new_mmr}**", parse_mode="Markdown")
    except ValueError:
        await message.answer("Numbers only.")


@dp.message(F.text == "📊 Stats")
async def cmd_stats(message: types.Message):
    # just a placeholder for now
    await message.answer("Stats update when game ends.")


@dp.message(F.text == "✅ WIN (+25)")
async def btn_win(message: types.Message):
    new_mmr = update_mmr(message.from_user.id, 25)
    await message.answer(f"So what? 📈 Ur pts: **{new_mmr}**", parse_mode="Markdown")


@dp.message(F.text == "❌ LOSE (-25)")
async def btn_lose(message: types.Message):
    new_mmr = update_mmr(message.from_user.id, -25)
    await message.answer(f"As expected. 📉 Ur pts: **{new_mmr}**", parse_mode="Markdown")


@dp.message()
async def manual_input(message: types.Message):
    text = message.text.replace(" ", "")
    # ignore commands
    if text.startswith("/"):
        return

    try:
        delta = int(text)
        new_mmr = update_mmr(message.from_user.id, delta)
        emoji = "📈" if delta > 0 else "📉"
        await message.answer(f"Accepted ({delta}). {emoji} Ur pts: **{new_mmr}**", parse_mode="Markdown", reply_markup=get_keyboard())
    except ValueError:
        pass  # ignore non-number text


async def main():
    # start web server for keep-alive
    await start_web_server()
    # start bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
