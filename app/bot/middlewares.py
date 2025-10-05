"""
Middleware для бота
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.core.db import db_manager

logger = logging.getLogger(__name__)


class UserRegistrationMiddleware(BaseMiddleware):
    """Middleware для автоматической регистрации пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Обработка события"""
        
        # Получаем информацию о пользователе
        user = event.from_user
        
        if user:
            try:
                # Регистрируем или обновляем пользователя
                await db_manager.register_user(
                    user_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name
                )
            except Exception as e:
                logger.error(f"Error registering user {user.id}: {e}")
        
        # Продолжаем обработку
        return await handler(event, data)

