from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Account, Meter, MeterType, Reading, ReadingStatus
from app.services.validation import validate_reading


async def get_account_by_number(db: AsyncSession, external_number: str) -> Account | None:
    result = await db.execute(
        select(Account).where(Account.external_number == external_number.strip())
    )
    return result.scalar_one_or_none()


async def get_meter(
    db: AsyncSession,
    account_id: int,
    meter_type: MeterType,
) -> Meter | None:
    result = await db.execute(
        select(Meter).where(
            Meter.account_id == account_id,
            Meter.meter_type == meter_type,
        )
    )
    return result.scalar_one_or_none()


async def create_reading(
    db: AsyncSession,
    meter: Meter,
    period: str,
    photo_path: str,
    recognized_value: float | None,
    confidence: float = 0.0,
    raw_text: str = "",
) -> Reading:
    reading = Reading(
        meter_id=meter.id,
        period=period,
        photo_path=photo_path,
        recognized_value=recognized_value,
        status=ReadingStatus.RECOGNIZED if recognized_value else ReadingStatus.NEW,
        ocr_confidence=confidence,
        ocr_raw_text=raw_text[:4000],
    )

    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


async def confirm_reading(db: AsyncSession, reading: Reading, value: float) -> Reading:
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
    await db.refresh(reading)
    return reading