import csv
import io
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import verify_admin_token
from app.api.schemas import AccountImport, ReadingOut, ReadingUpdate
from app.core.database import get_db
from app.models.models import Account, Meter, Reading, ReadingStatus
from app.services.ocr import get_ocr_provider
from app.services.readings import confirm_reading

router = APIRouter(prefix="/api/v1", tags=["MVP"])
PHOTOS_DIR = Path("photos")
PHOTOS_DIR.mkdir(exist_ok=True)


@router.post("/accounts/import")
async def import_accounts(
    items: list[AccountImport],
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    created_accounts = 0
    created_meters = 0

    for item in items:
        existing = await db.execute(
            select(Account).where(Account.external_number == item.external_number)
        )
        account = existing.scalar_one_or_none()

        if not account:
            account = Account(
                external_number=item.external_number,
                address=item.address,
            )
            db.add(account)
            await db.flush()
            created_accounts += 1

        for meter_data in item.meters:
            meter = Meter(
                account_id=account.id,
                meter_type=meter_data.meter_type,
                serial_number=meter_data.serial_number,
                previous_value=meter_data.previous_value,
            )
            db.add(meter)
            created_meters += 1

    await db.commit()

    return {
        "accounts_created": created_accounts,
        "meters_created": created_meters,
    }


@router.post("/readings/{meter_id}/photo", response_model=ReadingOut)
async def upload_photo(
    meter_id: int,
    period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    meter = await db.get(Meter, meter_id)

    if not meter:
        raise HTTPException(status_code=404, detail="Meter not found")

    existing = await db.execute(
        select(Reading).where(
            Reading.meter_id == meter_id,
            Reading.period == period,
        )
    )

    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Reading already exists for this period",
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    photo_path = PHOTOS_DIR / f"{meter_id}_{datetime.utcnow().timestamp()}.jpg"
    photo_path.write_bytes(content)

    provider = get_ocr_provider()
    ocr_result = await provider.recognize(content)

    reading = Reading(
        meter_id=meter_id,
        period=period,
        photo_path=str(photo_path),
        recognized_value=ocr_result.value,
        status=ReadingStatus.RECOGNIZED if ocr_result.value else ReadingStatus.NEW,
        validation_message=ocr_result.error or "",
        ocr_confidence=ocr_result.confidence,
        ocr_raw_text=ocr_result.raw_text[:4000],
    )

    db.add(reading)
    await db.commit()
    await db.refresh(reading)

    return reading


@router.post("/readings/{reading_id}/confirm", response_model=ReadingOut)
async def confirm(
    reading_id: int,
    value: float,
    db: AsyncSession = Depends(get_db),
):
    reading = await db.get(Reading, reading_id)

    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    return await confirm_reading(db, reading, value)


@router.get("/readings", response_model=list[ReadingOut])
async def list_readings(
    period: str | None = None,
    status: ReadingStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Reading).order_by(Reading.id.desc())

    if period:
        query = query.where(Reading.period == period)

    if status:
        query = query.where(Reading.status == status)

    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/readings/{reading_id}", response_model=ReadingOut)
async def update_reading(
    reading_id: int,
    payload: ReadingUpdate,
    db: AsyncSession = Depends(get_db),
):
    reading = await db.get(Reading, reading_id)

    if not reading:
        raise HTTPException(status_code=404, detail="Reading not found")

    if payload.confirmed_value is not None:
        return await confirm_reading(db, reading, payload.confirmed_value)

    if payload.status:
        reading.status = payload.status

    await db.commit()
    await db.refresh(reading)
    return reading


@router.get("/readings/export")
async def export_csv(
    period: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_token),
):
    result = await db.execute(
        select(Reading).where(
            Reading.period == period,
            Reading.status == ReadingStatus.CONFIRMED,
        )
    )
    readings = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "reading_id",
        "meter_id",
        "period",
        "confirmed_value",
        "created_at",
    ])

    for reading in readings:
        writer.writerow([
            reading.id,
            reading.meter_id,
            reading.period,
            reading.confirmed_value,
            reading.created_at,
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=readings_{period}.csv"
        },
    )