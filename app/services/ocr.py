import base64
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class OCRResult:
    value: float | None
    confidence: float
    raw_text: str
    error: str | None = None


YANDEX_OCR_URL = "https://ai.api.cloud.yandex.net/ocr/v1/recognizeText"


class YandexVisionOCR:
    async def recognize(self, image_bytes: bytes) -> OCRResult:
        if not settings.yandex_api_key or not settings.yandex_folder_id:
            return OCRResult(
                value=None,
                confidence=0.0,
                raw_text="",
                error="Не заданы YANDEX_API_KEY или YANDEX_FOLDER_ID",
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {settings.yandex_api_key}",
            "x-folder-id": settings.yandex_folder_id,
        }

        payload = {
            "mimeType": "JPEG",
            "languageCodes": ["ru", "en"],
            "model": "page",
            "content": base64.b64encode(image_bytes).decode("utf-8"),
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    YANDEX_OCR_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return OCRResult(
                value=None,
                confidence=0.0,
                raw_text="",
                error=f"Ошибка Yandex Vision: {exc.response.status_code}",
            )
        except Exception as exc:
            return OCRResult(
                value=None,
                confidence=0.0,
                raw_text="",
                error=f"Ошибка запроса к OCR: {exc}",
            )

        raw_text = self._extract_text(data)
        value, confidence = self._extract_meter_value(raw_text)

        if value is None:
            return OCRResult(
                value=None,
                confidence=confidence,
                raw_text=raw_text,
                error="Не удалось распознать показание",
            )

        return OCRResult(
            value=value,
            confidence=confidence,
            raw_text=raw_text,
        )

    def _extract_text(self, data: dict) -> str:
        lines = []

        for annotation in data.get("result", {}).get("textAnnotations", []):
            for page in annotation.get("pages", []):
                for block in page.get("blocks", []):
                    for line in block.get("lines", []):
                        text = line.get("text", "")
                        if text:
                            lines.append(text)

        return "\n".join(lines)

    def _extract_meter_value(self, raw_text: str) -> tuple[float | None, float]:
        candidates = re.findall(r"\b\d{1,6}[.,]\d{3}\b", raw_text)

        if candidates:
            value = float(candidates[-1].replace(",", "."))
            return value, 0.85

        digits = re.findall(r"\d+", raw_text)
        joined = "".join(digits)

        if len(joined) >= 4:
            whole = joined[:-3]
            fraction = joined[-3:]

            try:
                return float(f"{whole}.{fraction}"), 0.55
            except ValueError:
                pass

        return None, 0.0


class StubOCRProvider:
    async def recognize(self, image_bytes: bytes) -> OCRResult:
        return OCRResult(
            value=None,
            confidence=0.0,
            raw_text="",
            error="OCR-провайдер не настроен",
        )


def get_ocr_provider():
    if settings.ocr_provider == "yandex":
        return YandexVisionOCR()

    return StubOCRProvider()