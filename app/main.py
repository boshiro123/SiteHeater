"""
Главный модуль приложения
"""
import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.core.db import db_manager
from app.core.scheduler import warming_scheduler
from app.utils.logger import setup_logging

# Импорт обработчиков
from app.bot.handlers import start, add_domain, domains, help

logger = logging.getLogger(__name__)


class SiteHeaterApp:
    """Главное приложение"""
    
    def __init__(self):
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.shutdown_event = asyncio.Event()
    
    async def on_startup(self):
        """Действия при запуске"""
        logger.info("🚀 Starting SiteHeater...")
        
        # Валидация конфигурации
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)
        
        # Инициализация базы данных
        try:
            await db_manager.init_db()
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}", exc_info=True)
            sys.exit(1)
        
        # Запуск планировщика
        try:
            warming_scheduler.start()
            await warming_scheduler.reload_jobs()
            logger.info("✅ Scheduler started")
        except Exception as e:
            logger.error(f"❌ Scheduler start error: {e}", exc_info=True)
            sys.exit(1)
        
        logger.info("✨ SiteHeater started successfully!")
    
    async def on_shutdown(self):
        """Действия при остановке"""
        logger.info("🛑 Shutting down SiteHeater...")
        
        # Остановка планировщика
        try:
            warming_scheduler.shutdown()
            logger.info("✅ Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        
        # Закрытие соединения с БД
        try:
            await db_manager.close()
            logger.info("✅ Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")
        
        logger.info("👋 SiteHeater stopped")
    
    def setup_handlers(self):
        """Регистрация обработчиков"""
        self.dp.include_router(start.router)
        self.dp.include_router(help.router)
        self.dp.include_router(add_domain.router)
        self.dp.include_router(domains.router)
        
        logger.info("✅ Handlers registered")
    
    async def run(self):
        """Запуск бота"""
        # Настройка логирования
        setup_logging()
        
        # Создание бота и диспетчера
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher(storage=MemoryStorage())
        
        # Регистрация обработчиков
        self.setup_handlers()
        
        # Регистрация событий старта/остановки
        self.dp.startup.register(self.on_startup)
        self.dp.shutdown.register(self.on_shutdown)
        
        # Запуск polling
        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types(),
            )
        except Exception as e:
            logger.error(f"❌ Error in polling: {e}", exc_info=True)
        finally:
            await self.bot.session.close()


async def main():
    """Точка входа"""
    app = SiteHeaterApp()
    
    # Обработка сигналов для graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        loop.create_task(app.on_shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())

