"""
S3 Storage Module for Meter Reader Bot
Supports AWS S3 and compatible storage (MinIO, Yandex Cloud, etc.)
"""

import os
import uuid
import logging
from typing import Optional, Tuple
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logging.warning("boto3 not installed. S3 functionality disabled.")

logger = logging.getLogger(__name__)


class S3Storage:
    """
    Класс для работы с S3-хранилищем для сохранения фото показаний счетчиков.
    
    Поддерживает:
    - AWS S3
    - Yandex Cloud Object Storage
    - MinIO
    - Другие S3-совместимые хранилища
    """
    
    def __init__(self):
        """Инициализация S3 клиента из переменных окружения."""
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 library is required. Install with: pip install boto3")
        
        # Конфигурация из переменных окружения
        self.access_key = os.getenv('S3_ACCESS_KEY')
        self.secret_key = os.getenv('S3_SECRET_KEY')
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'meter-readings')
        self.region = os.getenv('S3_REGION', 'us-east-1')
        self.endpoint_url = os.getenv('S3_ENDPOINT_URL')  # Для совместимых хранилищ (MinIO, Yandex)
        self.use_ssl = os.getenv('S3_USE_SSL', 'true').lower() == 'true'
        
        # Префикс для организации файлов
        self.base_prefix = os.getenv('S3_BASE_PREFIX', 'readings')
        
        # Публичный URL базовый (если бакет публичный)
        self.public_url_base = os.getenv('S3_PUBLIC_URL_BASE')
        
        self.client = self._create_client()
    
    def _create_client(self):
        """Создание S3 клиента."""
        try:
            client_kwargs = {
                'aws_access_key_id': self.access_key,
                'aws_secret_access_key': self.secret_key,
                'region_name': self.region,
            }
            
            if self.endpoint_url:
                client_kwargs['endpoint_url'] = self.endpoint_url
            
            if not self.use_ssl:
                client_kwargs['use_ssl'] = False
            
            return boto3.client('s3', **client_kwargs)
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            raise
    
    def upload_photo(
        self, 
        file_bytes: bytes, 
        user_id: int, 
        meter_id: int,
        content_type: str = 'image/jpeg'
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Загрузка фото в S3.
        
        Args:
            file_bytes: Байты файла
            user_id: ID пользователя Telegram
            meter_id: ID прибора учета
            content_type: MIME тип файла
            
        Returns:
            Tuple[photo_url, photo_key] или (None, None) при ошибке
        """
        try:
            # Генерация уникального ключа
            timestamp = datetime.now().strftime('%Y/%m/%d')
            file_extension = self._get_extension(content_type)
            filename = f"{uuid.uuid4()}{file_extension}"
            
            # Структура папок: readings/{user_id}/{year}/{month}/{day}/{filename}
            key = f"{self.base_prefix}/{user_id}/{timestamp}/{filename}"
            
            # Загрузка в S3
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
                ACL='private'  # Приватный доступ по умолчанию
            )
            
            # Формирование URL
            if self.public_url_base:
                # Используем заданный публичный URL
                url = f"{self.public_url_base.rstrip('/')}/{key}"
            else:
                # Генерируем URL через boto3 (требует прав на получение URL)
                try:
                    url = self.client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.bucket_name, 'Key': key},
                        ExpiresIn=3600 * 24 * 365  # 1 год
                    )
                except Exception:
                    # Если не можем сгенерировать presigned URL, возвращаем None
                    url = None
            
            logger.info(f"Photo uploaded successfully: {key}")
            return url, key
            
        except NoCredentialsError:
            logger.error("S3 credentials not found")
            return None, None
        except ClientError as e:
            logger.error(f"S3 client error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error uploading photo: {e}")
            return None, None
    
    def get_photo_url(self, photo_key: str, expires_in: int = 3600) -> Optional[str]:
        """
        Получение временного URL для просмотра фото.
        
        Args:
            photo_key: Ключ объекта в S3
            expires_in: Время действия ссылки в секундах
            
        Returns:
            URL или None при ошибке
        """
        try:
            if self.public_url_base:
                return f"{self.public_url_base.rstrip('/')}/{photo_key}"
            
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': photo_key},
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            logger.error(f"Error generating photo URL: {e}")
            return None
    
    def delete_photo(self, photo_key: str) -> bool:
        """
        Удаление фото из S3.
        
        Args:
            photo_key: Ключ объекта в S3
            
        Returns:
            True если успешно, False иначе
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=photo_key
            )
            logger.info(f"Photo deleted: {photo_key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting photo: {e}")
            return False
    
    def _get_extension(self, content_type: str) -> str:
        """Получение расширения файла по MIME типу."""
        mime_to_ext = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
        }
        return mime_to_ext.get(content_type, '.bin')
    
    def test_connection(self) -> bool:
        """
        Проверка подключения к S3.
        
        Returns:
            True если подключение успешно
        """
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info("S3 connection test successful")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                logger.warning(f"Bucket '{self.bucket_name}' not found")
            else:
                logger.error(f"S3 connection test failed: {e}")
            return False
        except Exception as e:
            logger.error(f"S3 connection test error: {e}")
            return False


# Альтернативная реализация для локального хранения (если S3 недоступен)
class LocalStorage:
    """
    Локальное хранилище для фото (fallback вариант).
    Сохраняет файлы в локальную директорию.
    """
    
    def __init__(self, base_path: str = './storage/photos'):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def upload_photo(
        self, 
        file_bytes: bytes, 
        user_id: int, 
        meter_id: int,
        content_type: str = 'image/jpeg'
    ) -> Tuple[Optional[str], Optional[str]]:
        """Загрузка фото в локальное хранилище."""
        try:
            from datetime import datetime
            import uuid
            
            timestamp = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')
            file_extension = self._get_extension(content_type)
            filename = f"{user_id}_{meter_id}_{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
            
            # Создаем поддиректорию для пользователя
            user_dir = os.path.join(self.base_path, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            file_path = os.path.join(user_dir, filename)
            
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            
            # Возвращаем относительный путь как key и URL
            relative_path = f"photos/{user_id}/{filename}"
            url = f"/static/{relative_path}"  # Предполагается, что есть статический сервер
            
            logger.info(f"Photo saved locally: {file_path}")
            return url, relative_path
            
        except Exception as e:
            logger.error(f"Error saving photo locally: {e}")
            return None, None
    
    def get_photo_url(self, photo_key: str, expires_in: int = 0) -> Optional[str]:
        """Получение URL для локального фото."""
        if photo_key:
            return f"/static/{photo_key}"
        return None
    
    def delete_photo(self, photo_key: str) -> bool:
        """Удаление локального фото."""
        try:
            full_path = os.path.join(self.base_path, photo_key)
            if os.path.exists(full_path):
                os.remove(full_path)
                logger.info(f"Local photo deleted: {full_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting local photo: {e}")
            return False
    
    def _get_extension(self, content_type: str) -> str:
        """Получение расширения файла по MIME типу."""
        mime_to_ext = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
        }
        return mime_to_ext.get(content_type, '.bin')


def create_storage() -> S3Storage | LocalStorage:
    """
    Фабричная функция для создания хранилища.
    Пытается создать S3 хранилище, при неудаче - локальное.
    """
    if os.getenv('S3_ACCESS_KEY') and os.getenv('S3_SECRET_KEY') and os.getenv('S3_BUCKET_NAME'):
        try:
            storage = S3Storage()
            if storage.test_connection():
                logger.info("Using S3 storage")
                return storage
        except Exception as e:
            logger.warning(f"S3 initialization failed: {e}, falling back to local storage")
    
    logger.info("Using local storage")
    return LocalStorage()
