from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./meter_mvp.db"
    ocr_provider: str = "stub"
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    admin_token: str = "change_this_admin_token"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()