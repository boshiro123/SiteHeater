"""
Обработчик команды /status - просмотр активных прогревов
"""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.core.warming_manager import warming_manager

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status - показывает активные прогревы"""
    active_count = warming_manager.get_active_count()
    
    if active_count == 0:
        await message.answer(
            "💤 <b>Нет активных прогревов</b>\n\n"
            "Используйте /domains для запуска прогрева.",
            parse_mode="HTML"
        )
        return
    
    # Формируем список активных прогревов
    status_lines = [f"🔥 <b>Активных прогревов: {active_count}</b>\n"]
    
    for domain_id, info in warming_manager.task_info.items():
        if warming_manager.is_warming(domain_id):
            elapsed = (datetime.utcnow() - info["start_time"]).total_seconds()
            elapsed_str = f"{int(elapsed // 60)}м {int(elapsed % 60)}с"
            
            status_lines.append(
                f"\n🌐 <b>{info['domain_name']}</b>\n"
                f"  📊 Страниц: {info['urls_count']}\n"
                f"  ⏱ Время: {elapsed_str}"
            )
    
    await message.answer(
        "\n".join(status_lines),
        parse_mode="HTML"
    )

