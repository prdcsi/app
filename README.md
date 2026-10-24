# MVP: передача показаний счётчиков по фото

Минимальный сервис для УК:
- Telegram-бот принимает фото счётчиков ХВС/ГВС;
- житель подтверждает распознанное значение;
- сервис валидирует показание;
- УК просматривает и выгружает данные.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# укажите BOT_TOKEN в .env
uvicorn app.main:app --reload
python -m app.bot
```

## Что уже реализовано
- FastAPI: импорт ЛС, приём показаний, статусы, экспорт CSV.
- Telegram-бот: выбор ЛС, прибора, фото, подтверждение значения.
- Валидация: рост значения, дельта, дубликаты, разрядность.
- OCR-провайдер-заглушка; подключите Yandex Vision или другой API в `app/services/ocr.py`.

## Следующий шаг
Подключите реального OCR-провайдера и импортируйте лицевые счета УК из Excel.
