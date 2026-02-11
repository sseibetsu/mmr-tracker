import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy import create_engine, Column, Integer, BigInteger
from sqlalchemy.orm import declarative_base, sessionmaker

# bot settings
API_TOKEN = ''
DB_NAME = 'dota_mmr.db'

Base = declarative_base()


class UserMMR(Base):
    __tablename__ = 'users'
    user_id = Column(BigInteger, primary_key=True)
    current_mmr = Column(Integer, default=0)
    wins_today = Column(Integer, default=0)
    loss_today = Column(Integer, default=0)


engine = create_engine(f'sqlite:///{DB_NAME}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# bot
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


def get_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ WIN (+25)")
    builder.button(text="❌ LOSE (-25)")
    builder.button(text="📊 Stats")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def update_mmr(user_id, delta):
    session = Session()
    user = session.query(UserMMR).filter_by(user_id=user_id).first()

    if not user:
        user = UserMMR(user_id=user_id, current_mmr=3000)
        session.add(user)

    user.current_mmr += delta
    if delta > 0:
        user.wins_today += 1
    elif delta < 0:
        user.loss_today += 1

    new_mmr = user.current_mmr
    session.commit()
    session.close()
    return new_mmr


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Sup, I'm tracking ur pts in dota. \n"
        "Press buttons or write numbers (e.g.: +30, -20).",
        reply_markup=get_keyboard()
    )


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
    try:
        delta = int(text)
        new_mmr = update_mmr(message.from_user.id, delta)
        emoji = "📈" if delta > 0 else "📉"
        await message.answer(f"Accepted ({delta}). {emoji} Ur pts: **{new_mmr}**", parse_mode="Markdown", reply_markup=get_keyboard())
    except ValueError:
        await message.answer("I only understand buttons or numbers (e.g.: -30, +40).")


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
