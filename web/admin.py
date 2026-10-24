import base64

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Reading, ReadingStatus

router = APIRouter(tags=["Admin"])


@router.get("/admin/readings", response_class=HTMLResponse)
async def admin_readings(
    status: ReadingStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Reading).order_by(Reading.id.desc()).limit(100)

    if status:
        query = query.where(Reading.status == status)

    result = await db.execute(query)
    readings = result.scalars().all()

    rows = ""

    for reading in readings:
        rows += f"""
        <tr>
            <td>{reading.id}</td>
            <td>{reading.meter_id}</td>
            <td>{reading.period}</td>
            <td>{reading.recognized_value or "-"}</td>
            <td>{reading.confirmed_value or "-"}</td>
            <td>{reading.status.value}</td>
            <td>{reading.validation_message or "-"}</td>
            <td>
                <a href="/admin/readings/{reading.id}/photo" target="_blank">
                    фото
                </a>
            </td>
        </tr>
        """

    html = f"""
    <!doctype html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>Показания — MVP</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; }}
            th {{ background: #f4f4f4; text-align: left; }}
        </style>
    </head>
    <body>
        <h1>Последние показания</h1>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Прибор</th>
                    <th>Период</th>
                    <th>Распознано</th>
                    <th>Подтверждено</th>
                    <th>Статус</th>
                    <th>Комментарий</th>
                    <th>Фото</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@router.get("/admin/readings/{reading_id}/photo")
async def reading_photo(
    reading_id: int,
    db: AsyncSession = Depends(get_db),
):
    reading = await db.get(Reading, reading_id)

    if not reading:
        return HTMLResponse("Not found", status_code=404)

    try:
        with open(reading.photo_path, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        return HTMLResponse("Photo not found", status_code=404)

    encoded = base64.b64encode(content).decode()

    return HTMLResponse(
        content=f"""
        <img
            src="data:image/jpeg;base64,{encoded}"
            style="max-width: 100%"
        >
        """
    )