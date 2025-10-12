"""
Middleware для проверки ролей
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.core.db import db_manager

logger = logging.getLogger(__name__)


class AdminOnlyMiddleware(BaseMiddleware):
    """Middleware для проверки прав администратора"""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # Получаем пользователя из БД
        user = await db_manager.get_or_create_user(
            user_id=user_id,
            username=event.from_user.username,
            first_name=event.from_user.first_name,
            last_name=event.from_user.last_name
        )
        
        # Проверяем роль
        if user.role != "admin":
            if isinstance(event, Message):
                await event.answer(
                    "❌ <b>Недостаточно прав</b>\n\n"
                    "Эта команда доступна только администраторам.",
                    parse_mode="HTML"
                )
            else:  # CallbackQuery
                await event.answer(
                    "❌ Недостаточно прав. Только для администраторов.",
                    show_alert=True
                )
            return
        
        # Продолжаем обработку
        return await handler(event, data)

