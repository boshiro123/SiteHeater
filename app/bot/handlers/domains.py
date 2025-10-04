"""
Обработчики работы с доменами
"""
import logging
import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards.inline import (
    get_domains_keyboard,
    get_domain_actions_keyboard,
    get_schedule_keyboard,
    get_delete_confirm_keyboard,
)
from app.core.db import db_manager
from app.core.warmer import warmer
from app.core.scheduler import warming_scheduler

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("domains"))
async def cmd_domains(message: Message):
    """Команда /domains - список доменов"""
    domains = await db_manager.get_all_domains(user_id=message.from_user.id)
    
    if not domains:
        await message.answer(
            "📭 У вас пока нет добавленных доменов.\n\n"
            "Используйте /add для добавления домена."
        )
        return
    
    await message.answer(
        f"📋 <b>Ваши домены ({len(domains)}):</b>\n\n"
        f"Выберите домен для управления:",
        parse_mode="HTML",
        reply_markup=get_domains_keyboard(domains)
    )


@router.callback_query(F.data == "back_to_domains")
async def callback_back_to_domains(callback: CallbackQuery):
    """Возврат к списку доменов"""
    await callback.answer()
    
    domains = await db_manager.get_all_domains(user_id=callback.from_user.id)
    
    if not domains:
        await callback.message.edit_text(
            "📭 У вас нет доменов.\n\n"
            "Используйте /add для добавления."
        )
        return
    
    await callback.message.edit_text(
        f"📋 <b>Ваши домены ({len(domains)}):</b>\n\n"
        f"Выберите домен для управления:",
        parse_mode="HTML",
        reply_markup=get_domains_keyboard(domains)
    )


@router.callback_query(F.data.startswith("domain_"))
async def callback_domain_info(callback: CallbackQuery):
    """Информация о домене"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[1])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    # Проверяем, есть ли активная задача
    has_active_job = any(job.active for job in domain.jobs)
    
    status_text = "🟢 Активен" if domain.is_active else "🔴 Неактивен"
    urls_count = len(domain.urls)
    
    job_info = ""
    if has_active_job:
        active_job = next((job for job in domain.jobs if job.active), None)
        if active_job:
            job_info = f"\n⏰ Расписание: <b>{active_job.schedule}</b>"
            if active_job.last_run:
                job_info += f"\n🕒 Последний запуск: {active_job.last_run.strftime('%Y-%m-%d %H:%M')}"
    
    await callback.message.edit_text(
        f"🌐 <b>{domain.name}</b>\n\n"
        f"Статус: {status_text}\n"
        f"📊 Страниц: <b>{urls_count}</b>\n"
        f"📅 Добавлен: {domain.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{job_info}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_domain_actions_keyboard(domain_id, has_active_job)
    )


@router.callback_query(F.data.startswith("warm_once_"))
async def callback_warm_once(callback: CallbackQuery):
    """Разовый прогрев домена"""
    await callback.answer("🔥 Запускаю прогрев...")
    
    domain_id = int(callback.data.split("_")[2])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.message.answer("❌ Домен не найден или нет URL.")
        return
    
    # Отправляем сообщение о начале прогрева
    status_msg = await callback.message.answer(
        f"🔥 Начинаю прогрев <b>{domain.name}</b>...\n"
        f"Страниц: {len(domain.urls)}",
        parse_mode="HTML"
    )
    
    try:
        # Запускаем прогрев
        urls = [url.url for url in domain.urls]
        stats = await warmer.warm_site(urls)
        
        # Формируем отчет
        success_rate = (stats["success"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0
        
        await status_msg.edit_text(
            f"✅ <b>Прогрев завершен!</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"📊 Всего запросов: <b>{stats['total_requests']}</b>\n"
            f"✅ Успешно: <b>{stats['success']}</b> ({success_rate:.1f}%)\n"
            f"⏱ Таймауты: <b>{stats['timeout']}</b>\n"
            f"❌ Ошибки: <b>{stats['error']}</b>\n"
            f"⏱ Среднее время: <b>{stats['avg_time']:.2f}s</b>\n"
            f"⏱ Общее время: <b>{stats['total_time']:.2f}s</b>",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error warming domain {domain.name}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Ошибка при прогреве: {str(e)}"
        )


@router.callback_query(F.data.startswith("schedule_"))
async def callback_schedule(callback: CallbackQuery):
    """Настройка расписания"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[1])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    await callback.message.edit_text(
        f"⏰ <b>Настройка расписания для {domain.name}</b>\n\n"
        f"Выберите частоту прогрева:",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard(domain_id)
    )


@router.callback_query(F.data.startswith("set_schedule_"))
async def callback_set_schedule(callback: CallbackQuery):
    """Установка расписания"""
    await callback.answer("⏰ Настраиваю расписание...")
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    schedule = parts[3]
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    try:
        # Создаем задачу в базе
        job = await db_manager.create_job(domain_id, schedule, active=True)
        
        # Добавляем в планировщик
        success = warming_scheduler.add_job(domain_id, job.id, schedule)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Расписание установлено!</b>\n\n"
                f"🌐 Домен: <b>{domain.name}</b>\n"
                f"⏰ Частота: <b>{schedule}</b>\n\n"
                f"Прогрев будет выполняться автоматически.",
                parse_mode="HTML",
                reply_markup=get_domain_actions_keyboard(domain_id, has_active_job=True)
            )
        else:
            await callback.message.edit_text(
                f"❌ Ошибка при настройке расписания."
            )
        
    except Exception as e:
        logger.error(f"Error setting schedule for domain {domain_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}"
        )


@router.callback_query(F.data.startswith("stop_schedule_"))
async def callback_stop_schedule(callback: CallbackQuery):
    """Остановка расписания"""
    await callback.answer("⏹ Останавливаю...")
    
    domain_id = int(callback.data.split("_")[2])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    try:
        # Деактивируем задачи в базе
        await db_manager.deactivate_jobs_for_domain(domain_id)
        
        # Удаляем из планировщика
        warming_scheduler.remove_job(domain_id)
        
        await callback.message.edit_text(
            f"⏹ <b>Расписание остановлено</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n\n"
            f"Автоматический прогрев отключен.",
            parse_mode="HTML",
            reply_markup=get_domain_actions_keyboard(domain_id, has_active_job=False)
        )
        
    except Exception as e:
        logger.error(f"Error stopping schedule for domain {domain_id}: {e}", exc_info=True)
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data.startswith("show_urls_"))
async def callback_show_urls(callback: CallbackQuery):
    """Показать список URL домена"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[2])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.message.answer("❌ URL не найдены.")
        return
    
    # Формируем список URL
    urls_text = "\n".join(f"{i+1}. {url.url}" for i, url in enumerate(domain.urls[:20]))
    
    if len(domain.urls) > 20:
        urls_text += f"\n\n... и еще {len(domain.urls) - 20} URL"
    
    await callback.message.answer(
        f"📋 <b>URL для {domain.name}</b>\n\n"
        f"Всего: <b>{len(domain.urls)}</b>\n\n"
        f"{urls_text}",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("delete_"))
async def callback_delete(callback: CallbackQuery):
    """Подтверждение удаления домена"""
    await callback.answer()
    
    # Проверяем, это не confirm_delete
    if callback.data.startswith("delete_") and not callback.data.startswith("confirm_delete_"):
        domain_id = int(callback.data.split("_")[1])
        domain = await db_manager.get_domain_by_id(domain_id)
        
        if not domain:
            await callback.message.edit_text("❌ Домен не найден.")
            return
        
        await callback.message.edit_text(
            f"⚠️ <b>Удаление домена</b>\n\n"
            f"Вы уверены, что хотите удалить <b>{domain.name}</b>?\n\n"
            f"Это действие нельзя отменить.",
            parse_mode="HTML",
            reply_markup=get_delete_confirm_keyboard(domain_id)
        )


@router.callback_query(F.data.startswith("confirm_delete_"))
async def callback_confirm_delete(callback: CallbackQuery):
    """Подтверждение удаления домена"""
    await callback.answer("🗑 Удаляю...")
    
    domain_id = int(callback.data.split("_")[2])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    domain_name = domain.name
    
    try:
        # Останавливаем задачи
        warming_scheduler.remove_job(domain_id)
        
        # Удаляем из базы
        success = await db_manager.delete_domain(domain_id)
        
        if success:
            await callback.message.edit_text(
                f"✅ Домен <b>{domain_name}</b> успешно удален.",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("❌ Ошибка при удалении домена.")
        
    except Exception as e:
        logger.error(f"Error deleting domain {domain_id}: {e}", exc_info=True)
        await callback.message.edit_text(f"❌ Ошибка: {str(e)}")

