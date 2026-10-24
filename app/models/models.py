from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeterType(str, Enum):
    COLD_WATER = "cold_water"
    HOT_WATER = "hot_water"


class ReadingStatus(str, Enum):
    NEW = "new"
    RECOGNIZED = "recognized"
    CONFIRMED = "confirmed"
    REVIEW = "review"
    REJECTED = "rejected"
    EXPORTED = "exported"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(default=1)
    external_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    address: Mapped[str] = mapped_column(String(255), default="")
    telegram_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    meters: Mapped[list["Meter"]] = relationship(back_populates="account")


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    meter_type: Mapped[MeterType] = mapped_column(SAEnum(MeterType))
    serial_number: Mapped[str] = mapped_column(String(64), default="")
    previous_value: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    previous_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    account: Mapped[Account] = relationship(back_populates="meters")
    readings: Mapped[list["Reading"]] = relationship(back_populates="meter")


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("meter_id", "period", name="uq_meter_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    meter_id: Mapped[int] = mapped_column(ForeignKey("meters.id"), index=True)
    period: Mapped[str] = mapped_column(String(7), index=True)
    photo_path: Mapped[str] = mapped_column(String(512))
    recognized_value: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    confirmed_value: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    status: Mapped[ReadingStatus] = mapped_column(
        SAEnum(ReadingStatus),
        default=ReadingStatus.NEW,
    )
    validation_message: Mapped[str] = mapped_column(String(500), default="")
    ocr_confidence: Mapped[float] = mapped_column(default=0.0)
    ocr_raw_text: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    meter: Mapped[Meter] = relationship(back_populates="readings")