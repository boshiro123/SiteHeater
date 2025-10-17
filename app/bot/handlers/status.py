"""
Обработчик команды /status - просмотр активных прогревов и запланированных задач
"""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.core.warming_manager import warming_manager
from app.core.db import db_manager

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status - показывает активные прогревы и запланированные задачи"""
    
    # Получаем активные прогревы
    active_count = warming_manager.get_active_count()
    
    status_text = "📊 <b>Статус системы</b>\n\n"
    
    # 1. Активные прогревы (прямо сейчас)
    if active_count > 0:
        status_text += f"🔥 <b>Активных прогревов: {active_count}</b>\n"
        
        for domain_id, info in warming_manager.task_info.items():
            if warming_manager.is_warming(domain_id):
                elapsed = (datetime.utcnow() - info["start_time"]).total_seconds()
                elapsed_str = f"{int(elapsed // 60)}м {int(elapsed % 60)}с"
                
                status_text += (
                    f"\n🌐 <b>{info['domain_name']}</b>\n"
                    f"  📊 Страниц: {info['urls_count']}\n"
                    f"  ⏱ Время: {elapsed_str}\n"
                )
    else:
        status_text += "💤 Нет активных прогревов\n"
    
    # 2. Запланированные задачи (автопрогрев)
    status_text += "\n⏰ <b>Автопрогрев:</b>\n\n"
    
    # Получаем все домены с активными задачами
    domains = await db_manager.get_all_domains()
    scheduled_count = 0
    
    for domain in domains:
        active_jobs = [job for job in domain.jobs if job.active]
        if active_jobs:
            scheduled_count += 1
            job = active_jobs[0]
            
            last_run_text = ""
            if job.last_run:
                time_since = (datetime.utcnow() - job.last_run).total_seconds()
                if time_since < 3600:
                    last_run_text = f" (прогрев {int(time_since / 60)}м назад)"
                elif time_since < 86400:
                    last_run_text = f" (прогрев {int(time_since / 3600)}ч назад)"
            
            status_text += f"• {domain.name} - каждые {job.schedule}{last_run_text}\n"
    
    if scheduled_count == 0:
        status_text += "Нет запланированных задач\n"
    else:
        status_text += f"\n<i>Всего доменов в автопрогреве: {scheduled_count}</i>"
    
    await message.answer(status_text, parse_mode="HTML")

