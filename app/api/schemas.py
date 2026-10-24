from datetime import datetime

from pydantic import BaseModel, Field

from app.models.models import MeterType, ReadingStatus


class MeterImport(BaseModel):
    meter_type: MeterType
    serial_number: str = ""
    previous_value: float | None = None


class AccountImport(BaseModel):
    external_number: str
    address: str = ""
    meters: list[MeterImport] = Field(default_factory=list)


class ReadingOut(BaseModel):
    id: int
    meter_id: int
    period: str
    photo_path: str
    recognized_value: float | None
    confirmed_value: float | None
    status: ReadingStatus
    validation_message: str
    ocr_confidence: float
    created_at: datetime


class ReadingUpdate(BaseModel):
    confirmed_value: float | None = None
    status: ReadingStatus | None = None