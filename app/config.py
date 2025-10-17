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
    WARMER_CHUNK_SIZE: int = int(os.getenv("WARMER_CHUNK_SIZE", "400"))  # Размер части для разбиения больших доменов
    
    # Задержка между доменами для SaaS платформ (секунды, 0 = выключить)
    WARMER_DOMAIN_DELAY_MIN: int = int(os.getenv("WARMER_DOMAIN_DELAY_MIN", "0"))
    WARMER_DOMAIN_DELAY_MAX: int = int(os.getenv("WARMER_DOMAIN_DELAY_MAX", "60"))
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Notifications
    SEND_WARMING_NOTIFICATIONS: bool = os.getenv("SEND_WARMING_NOTIFICATIONS", "true").lower() == "true"
    
    # Technical channel for detailed warming reports (optional)
    # If set, warming notifications will be sent to this channel instead of admins
    # Example: -1001234567890 (channel ID)
    _technical_channel_id_raw = os.getenv("TECHNICAL_CHANNEL_ID", None)
    TECHNICAL_CHANNEL_ID: Optional[str] = _technical_channel_id_raw if _technical_channel_id_raw and _technical_channel_id_raw.strip() else None
    
    @classmethod
    def validate(cls) -> None:
        """Валидация конфигурации"""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")


config = Config()

