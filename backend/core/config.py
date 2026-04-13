from pydantic_settings import BaseSettings

from backend.core.logger_config import logger


class Settings(BaseSettings):
    BOT_TOKEN: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 0
    DB_POOL_TIMEOUT: int = 20
    DB_POOL_RECYCLE: int = 1800
    GPT_API_TOKEN: str
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_SYSTEM_PROMPT: str = "You are a helpful assistant. Answer briefly and clearly."

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def POSTGRES_ASYNC_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def POSTGRES_SYNC_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


try:
    settings = Settings()
    logger.info("Settings successfully loaded from .env")
except Exception:
    logger.error("Error loading settings from .env")
    raise
