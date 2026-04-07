# Настройка S3 хранилища для бота

## Обзор

Бот поддерживает сохранение фото показаний счетчиков в S3-совместимое хранилище. 
Если S3 не настроен, автоматически используется локальное хранилище.

## Поддерживаемые хранилища

- AWS S3
- Yandex Cloud Object Storage
- MinIO (self-hosted)
- Любое S3-совместимое хранилище

## Быстрый старт с MinIO (локально)

### 1. Запуск MinIO через Docker

```bash
docker run -d -p 9000:9000 -p 9001:9001 \
  --name minio \
  -e "MINIO_ROOT_USER=minioadmin" \
  -e "MINIO_ROOT_PASSWORD=minioadmin" \
  -v /data/minio:/data \
  minio/minio server /data --console-address ":9001"
```

### 2. Создание бакета

Откройте веб-консоль: http://localhost:9001
- Логин: `minioadmin`
- Пароль: `minioadmin`
- Создайте bucket с именем `meter-readings`

### 3. Настройка переменных окружения

```bash
export S3_ACCESS_KEY='minioadmin'
export S3_SECRET_KEY='minioadmin'
export S3_BUCKET_NAME='meter-readings'
export S3_ENDPOINT_URL='http://localhost:9000'
export S3_USE_SSL='false'
export S3_REGION='us-east-1'
```

## Настройка для Yandex Cloud

### 1. Создание бакета

1. Зайдите в консоль Yandex Cloud
2. Перейдите в Object Storage
3. Создайте новый bucket

### 2. Получение ключей

1. Создайте сервисный аккаунт
2. Создайте статический ключ доступа
3. Сохраните Access Key и Secret Key

### 3. Настройка переменных

```bash
export S3_ACCESS_KEY='YCA...ваш_ключ'
export S3_SECRET_KEY='...ваш_секрет'
export S3_BUCKET_NAME='ваш-bucket'
export S3_ENDPOINT_URL='https://storage.yandexcloud.net'
export S3_REGION='ru-central1'
export S3_USE_SSL='true'
```

## Настройка для AWS S3

### 1. Создание бакета

```bash
aws s3 mb s3://meter-readings-bucket --region us-east-1
```

### 2. Настройка IAM

Создайте политику для доступа к bucket:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::meter-readings-bucket/*"
        }
    ]
}
```

### 3. Переменные окружения

```bash
export S3_ACCESS_KEY='AKIA...'
export S3_SECRET_KEY='...'
export S3_BUCKET_NAME='meter-readings-bucket'
export S3_REGION='us-east-1'
export S3_USE_SSL='true'
```

## Структура файлов в S3

Файлы организуются по следующей структуре:

```
readings/
└── {user_id}/
    └── {year}/
        └── {month}/
            └── {day}/
                └── {uuid}.{extension}
```

Пример:
```
readings/123456789/2024/01/15/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg
```

## Проверка подключения

Запустите тестовый скрипт:

```python
from s3_storage import create_storage

storage = create_storage()

if storage.test_connection():
    print("✅ Подключение успешно!")
else:
    print("❌ Ошибка подключения")
```

## Переключение на локальное хранилище

Если нужно использовать локальное хранение вместо S3, просто не задавайте 
переменные окружения S3. Бот автоматически создаст папку `./storage/photos`.

## Безопасность

- Все файлы загружаются с ACL='private'
- Для просмотра генерируются presigned URL со сроком действия 1 час
- Рекомендуется использовать HTTPS для продакшена
