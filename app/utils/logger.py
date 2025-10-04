"""
Настройка логирования
"""
import logging
import sys
from app.config import config


def setup_logging():
    """Настройка логирования"""
    # Основной logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # Уменьшаем уровень логирования для сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
    
    return logger

