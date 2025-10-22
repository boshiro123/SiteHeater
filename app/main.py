"""
Главный модуль приложения
"""
import asyncio
import logging
import signal
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from app.config import config
from app.core.db import db_manager
from app.core.scheduler import warming_scheduler
from app.core.warming_manager import warming_manager
from app.utils.logger import setup_logging

# Импорт обработчиков
from app.bot.handlers import start, add_domain, domains, help, status, diagnostics, admin
from app.bot.middlewares import UserRegistrationMiddleware

logger = logging.getLogger(__name__)


class SiteHeaterApp:
    """Главное приложение"""
    
    def __init__(self):
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.shutdown_event = asyncio.Event()
    
    async def run_migrations(self):
        """Автоматический запуск миграций Alembic"""
        try:
            from alembic.config import Config
            from alembic import command
            import os
            
            # Получаем путь к alembic.ini
            alembic_cfg = Config("/app/alembic.ini")
            
            logger.info("📦 Running database migrations...")
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Database migrations completed")
        except Exception as e:
            logger.warning(f"⚠️ Migration warning (may be first run): {e}")
            # Не падаем, просто предупреждаем
    
    async def setup_bot_commands(self):
        """Установка команд бота (меню команд)"""
        try:
            # Команды для всех пользователей (базовые, для клиентов)
            default_commands = [
                BotCommand(command="start", description="🚀 Запустить бота"),
                BotCommand(command="domains", description="🌐 Мои сайты"),
                BotCommand(command="status", description="📊 Статус прогревов"),
                BotCommand(command="help", description="❓ Справка"),
            ]
            
            # Команды для администраторов (дополнительные)
            admin_commands = [
                BotCommand(command="start", description="🚀 Запустить бота"),
                BotCommand(command="help", description="❓ Справка"),
                BotCommand(command="domains", description="🌐 Все домены"),
                BotCommand(command="add", description="➕ Добавить домен"),
                BotCommand(command="add_client", description="👥 Добавить клиента"),
                BotCommand(command="clients", description="👥 Управление клиентами"),
                BotCommand(command="status", description="📊 Статус прогревов"),
                BotCommand(command="restore_backup", description="💾 Восстановить БД"),
            ]
            
            # Устанавливаем команды по умолчанию для всех пользователей
            await self.bot.set_my_commands(
                commands=default_commands,
                scope=BotCommandScopeDefault()
            )
            
            logger.info("✅ Bot commands configured")
        except Exception as e:
            logger.error(f"❌ Error setting bot commands: {e}", exc_info=True)
    
    async def on_startup(self):
        """Действия при запуске"""
        logger.info("🚀 Starting SiteHeater...")
        
        # Валидация конфигурации
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"❌ Configuration error: {e}")
            sys.exit(1)
        
        # Запуск миграций
        await asyncio.to_thread(self.run_migrations)
        
        # Инициализация базы данных
        try:
            await db_manager.init_db()
            logger.info("✅ Database initialized")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}", exc_info=True)
            sys.exit(1)
        
        # Установка команд бота
        await self.setup_bot_commands()
        
        # Логирование конфигурации уведомлений
        if config.SEND_WARMING_NOTIFICATIONS:
            if config.TECHNICAL_CHANNEL_ID:
                logger.info(f"📢 Warming notifications enabled → Technical channel: {config.TECHNICAL_CHANNEL_ID}")
            else:
                logger.info("📢 Warming notifications enabled → Admins")
        else:
            logger.info("📢 Warming notifications disabled")
        
        # Запуск планировщика
        try:
            # Устанавливаем экземпляр бота в планировщик для отправки уведомлений
            warming_scheduler.set_bot(self.bot)
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
        
        # Остановка всех активных прогревов
        try:
            await warming_manager.stop_all()
            logger.info("✅ All warming tasks stopped")
        except Exception as e:
            logger.error(f"Error stopping warming tasks: {e}")
        
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
        # Регистрируем middleware для автоматической регистрации пользователей
        self.dp.message.middleware(UserRegistrationMiddleware())
        self.dp.callback_query.middleware(UserRegistrationMiddleware())
        
        self.dp.include_router(start.router)
        self.dp.include_router(help.router)
        self.dp.include_router(admin.router)  # Роутер администраторов
        self.dp.include_router(status.router)
        self.dp.include_router(diagnostics.router)
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

