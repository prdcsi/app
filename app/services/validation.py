import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ValidationResult:
    ok: bool
    status: str
    message: str


def validate_reading(
    value: float,
    previous_value: float | None,
    previous_date: datetime | None,
    period: str,
) -> ValidationResult:
    if value < 0:
        return ValidationResult(False, "rejected", "Отрицательное значение недопустимо.")

    if previous_value is not None and value < float(previous_value):
        return ValidationResult(False, "rejected", "Новое показание меньше предыдущего.")

    if previous_value is not None:
        delta = value - float(previous_value)

        if delta == 0:
            return ValidationResult(False, "review", "Показание не изменилось с прошлого периода.")

        if delta > 100:
            return ValidationResult(
                False,
                "review",
                f"Подозрительно большой расход за период: {delta:.3f}.",
            )

    formatted = f"{value:.3f}"

    if not re.fullmatch(r"\d{1,6}\.\d{3}", formatted):
        return ValidationResult(False, "review", "Некорректный формат показания.")

    return ValidationResult(True, "confirmed", "OK")