"""
Конфигурация приложения
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Основная конфигурация приложения"""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://siteheater:siteheater_password@localhost:5432/siteheater"
    )
    
    # Warmer settings
    WARMER_CONCURRENCY: int = int(os.getenv("WARMER_CONCURRENCY", "5"))
    WARMER_MIN_DELAY: float = float(os.getenv("WARMER_MIN_DELAY", "0.5"))
    WARMER_MAX_DELAY: float = float(os.getenv("WARMER_MAX_DELAY", "2.0"))
    WARMER_REPEAT_COUNT: int = int(os.getenv("WARMER_REPEAT_COUNT", "2"))
    WARMER_REQUEST_TIMEOUT: int = int(os.getenv("WARMER_REQUEST_TIMEOUT", "30"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def validate(cls) -> None:
        """Валидация конфигурации"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")


config = Config()

