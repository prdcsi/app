import logging

from app.core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Account, Meter, MeterType, Reading, ReadingStatus
from app.services.ocr import get_ocr_provider
from app.services.validation import validate_reading

bot = Bot(token=settings.bot_token)
dp = Dispatcher()


class Flow(StatesGroup):
    account = State()
    meter = State()
    photo = State()
    confirm = State()


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Передать показания")]],
        resize_keyboard=True,
    )


@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте!\n"
        "Это сервис передачи показаний счётчиков по фото.\n\n"
        "Введите номер лицевого счёта.",
        reply_markup=main_keyboard(),
    )
    await state.set_state(Flow.account)


@dp.message(Flow.account, F.text)
async def enter_account(message: Message, state: FSMContext):
    async with SessionLocal() as db:
        result = await db.execute(
            select(Account).where(
                Account.external_number == message.text.strip()
            )
        )
        account = result.scalar_one_or_none()

    if not account:
        await message.answer(
            "Лицевой счёт не найден. Проверьте номер и попробуйте снова."
        )
        return

    await state.update_data(account_id=account.id)

    await message.answer(
        "Выберите прибор учёта:\n"
        "1 — Холодная вода\n"
        "2 — Горячая вода"
    )
    await state.set_state(Flow.meter)


@dp.message(Flow.meter, F.text)
async def choose_meter(message: Message, state: FSMContext):
    choice = message.text.strip()

    if choice == "1":
        meter_type = MeterType.COLD_WATER
    elif choice == "2":
        meter_type = MeterType.HOT_WATER
    else:
        await message.answer("Введите 1 или 2.")
        return

    data = await state.get_data()

    async with SessionLocal() as db:
        result = await db.execute(
            select(Meter).where(
                Meter.account_id == data["account_id"],
                Meter.meter_type == meter_type,
            )
        )
        meter = result.scalar_one_or_none()

    if not meter:
        await message.answer("Прибор учёта не найден. Обратитесь в УК.")
        return

    await state.update_data(meter_id=meter.id)

    await message.answer(
        "Сфотографируйте счётчик.\n\n"
        "Рекомендации:\n"
        "• снимайте циферблат целиком;\n"
        "• избегайте бликов;\n"
        "• в кадре должен быть только один счётчик."
    )
    await state.set_state(Flow.photo)


@dp.message(Flow.photo, F.photo)
async def receive_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    photo = message.photo[-1]

    file = await bot.get_file(photo.file_id)
    os.makedirs("photos", exist_ok=True)

    photo_path = f"photos/{photo.file_unique_id}.jpg"
    await bot.download_file(file.file_path, destination=photo_path)

    with open(photo_path, "rb") as f:
        image_bytes = f.read()

    provider = get_ocr_provider()
    ocr_result = await provider.recognize(image_bytes)

    period = datetime.utcnow().strftime("%Y-%m")

    async with SessionLocal() as db:
        meter = await db.get(Meter, data["meter_id"])

        existing = await db.execute(
            select(Reading).where(
                Reading.meter_id == meter.id,
                Reading.period == period,
            )
        )

        if existing.scalar_one_or_none():
            await message.answer("Показания за этот период уже приняты.")
            await state.clear()
            return

        reading = Reading(
            meter_id=meter.id,
            period=period,
            photo_path=photo_path,
            recognized_value=ocr_result.value,
            status=ReadingStatus.RECOGNIZED if ocr_result.value else ReadingStatus.NEW,
            validation_message=ocr_result.error or "",
            ocr_confidence=ocr_result.confidence,
            ocr_raw_text=ocr_result.raw_text[:4000],
        )

        db.add(reading)
        await db.commit()
        await db.refresh(reading)

    await state.update_data(
        reading_id=reading.id,
        value=ocr_result.value,
    )

    if ocr_result.value is None:
        await message.answer(
            "Не удалось распознать показание.\n"
            "Попробуйте переснять фото без бликов и с чётким циферблатом."
        )
        await state.set_state(Flow.photo)
        return

    await message.answer(
        f"Распознанное показание:\n"
        f"<b>{ocr_result.value:.3f}</b>\n\n"
        "Всё верно?\n"
        "Отправьте:\n"
        "• «да» — подтвердить;\n"
        "• либо правильное значение, например: 123,456."
    )
    await state.set_state(Flow.confirm)


@dp.message(Flow.confirm, F.text)
async def confirm_value(message: Message, state: FSMContext):
    data = await state.get_data()
    text = message.text.strip().lower()

    value = data.get("value") if text == "да" else None

    if value is None:
        try:
            value = float(text.replace(",", "."))
        except ValueError:
            await message.answer(
                "Отправьте «да» или число, например: 123,456."
            )
            return

    async with SessionLocal() as db:
        reading = await db.get(Reading, data["reading_id"])
        meter = await db.get(Meter, reading.meter_id)

        validation = validate_reading(
            value=value,
            previous_value=meter.previous_value,
            previous_date=meter.previous_date,
            period=reading.period,
        )

        reading.confirmed_value = value
        reading.status = ReadingStatus(validation.status)
        reading.validation_message = validation.message

        if validation.status == "confirmed":
            meter.previous_value = value
            meter.previous_date = datetime.utcnow()

        await db.commit()

    if validation.ok:
        await message.answer(
            f"Показания приняты:\n<b>{value:.3f}</b>\n\nСпасибо!",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            f"Показание сохранено на проверку.\n"
            f"Причина: {validation.message}"
        )

    await state.clear()


async def run():
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())