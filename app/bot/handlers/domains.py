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
    get_stats_period_keyboard,
    get_warming_group_keyboard,
)
from app.core.db import db_manager
from app.core.warmer import warmer
from app.core.scheduler import warming_scheduler
from app.core.warming_manager import warming_manager
from app.utils.graph import graph_generator
from app.utils.url_grouper import url_grouper
from datetime import datetime, timedelta
from aiogram.types import BufferedInputFile

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("domains"))
async def cmd_domains(message: Message):
    """Команда /domains - список доменов"""
    # Получаем пользователя для проверки роли
    user = await db_manager.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Админы видят ВСЕ домены, клиенты - только свои
    if user.role == "admin":
        domains = await db_manager.get_all_domains(user_id=None)
        title = "Все домены"
    else:
        domains = await db_manager.get_domains_by_client(user.id)
        title = "Ваши домены"
    
    if not domains:
        await message.answer(
            f"📭 {'Пока нет доменов' if user.role == 'admin' else 'У вас пока нет доменов'}.\n\n"
            f"{'Используйте /add для добавления домена.' if user.role == 'admin' else 'Обратитесь к администратору для добавления доменов.'}"
        )
        return
    
    await message.answer(
        f"📋 <b>{title} ({len(domains)}):</b>\n\n"
        f"Выберите домен для управления:",
        parse_mode="HTML",
        reply_markup=get_domains_keyboard(domains)
    )


@router.callback_query(F.data == "back_to_domains")
async def callback_back_to_domains(callback: CallbackQuery):
    """Возврат к списку доменов"""
    await callback.answer()
    
    # Получаем пользователя для проверки роли
    user = await db_manager.register_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
        last_name=callback.from_user.last_name
    )
    
    # Админы видят ВСЕ домены, клиенты - только свои
    if user.role == "admin":
        domains = await db_manager.get_all_domains(user_id=None)
        title = "Все домены"
    else:
        domains = await db_manager.get_domains_by_client(user.id)
        title = "Ваши домены"
    
    if not domains:
        await callback.message.edit_text("📭 Нет доменов.")
        return
    
    await callback.message.edit_text(
        f"📋 <b>{title} ({len(domains)}):</b>\n\n"
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
    
    text = (
        f"🌐 <b>{domain.name}</b>\n\n"
        f"Статус: {status_text}\n"
        f"📊 Страниц: <b>{urls_count}</b>\n"
        f"📅 Добавлен: {domain.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{job_info}\n\n"
        f"Выберите действие:"
    )
    
    # Безопасное редактирование сообщения
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_domain_actions_keyboard(domain_id, has_active_job)
        )
    except Exception:
        # Если не получилось отредактировать, удаляем старое и отправляем новое
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_domain_actions_keyboard(domain_id, has_active_job)
        )


# Более специфичный обработчик должен быть выше!
@router.callback_query(F.data.startswith("warm_group_"))
async def callback_warm_group(callback: CallbackQuery):
    """Запуск разового прогрева с выбранной группой"""
    await callback.answer("🔥 Запускаю прогрев...")
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    group = int(parts[3])
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.message.edit_text("❌ Домен не найден или нет URL.")
        return
    
    # Фильтруем URL по выбранной группе
    all_urls = [url.url for url in domain.urls]
    urls = url_grouper.filter_urls_by_group(all_urls, domain.name, group)
    
    logger.info(f"Warming domain {domain.name} (group {group}): {len(urls)}/{len(all_urls)} URLs")
    
    # Запускаем прогрев в фоновом режиме
    started = await warming_manager.start_warming(
        domain_id=domain_id,
        domain_name=domain.name,
        urls=urls,
        user_id=callback.from_user.id,
        bot=callback.bot
    )
    
    if started:
        active_count = warming_manager.get_active_count()
        await callback.answer("🔥 Прогрев запущен!", show_alert=False)
        await callback.message.answer(
            f"🚀 <b>Прогрев запущен в фоновом режиме</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"📊 Страниц: <b>{len(domain.urls)}</b>\n"
            f"🔥 Активных прогревов: <b>{active_count}</b>\n\n"
            f"Уведомление придет по завершении.",
            parse_mode="HTML"
        )
    else:
        await callback.answer(
            "⚠️ Не удалось запустить прогрев",
            show_alert=True
        )


@router.callback_query(F.data.startswith("warm_once_"))
async def callback_warm_once(callback: CallbackQuery):
    """Показать выбор группы для разового прогрева"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[2])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.answer("❌ Домен не найден или нет URL.", show_alert=True)
        return
    
    # Проверяем, не идет ли уже прогрев этого домена
    if warming_manager.is_warming(domain_id):
        await callback.answer(
            f"⚠️ Прогрев {domain.name} уже выполняется!",
            show_alert=True
        )
        return
    
    # Получаем статистику по группам
    all_urls = [url.url for url in domain.urls]
    stats = url_grouper.get_group_stats(all_urls, domain.name)
    
    await callback.message.edit_text(
        f"🔥 <b>Разовый прогрев</b>\n\n"
        f"🌐 Домен: <b>{domain.name}</b>\n\n"
        f"Выберите группу URL:\n"
        f"🏠 Группа 1: <b>{stats[1]}</b> страниц (только главная)\n"
        f"📄 Группа 2: <b>{stats[2]}</b> страниц (основные)\n"
        f"🌐 Группа 3: <b>{stats[3]}</b> страниц (все)",
        parse_mode="HTML",
        reply_markup=get_warming_group_keyboard(domain_id, action="warm")
    )


# Более специфичные обработчики должны быть ВЫШЕ!
@router.callback_query(F.data.startswith("set_schedule_"))
async def callback_set_schedule(callback: CallbackQuery):
    """Установка расписания"""
    await callback.answer("⏰ Настраиваю расписание...")
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    group = int(parts[3])
    schedule = parts[4]
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    try:
        # Создаем задачу в базе с выбранной группой
        job = await db_manager.create_job(domain_id, schedule, active=True, active_url_group=group)
        
        # Добавляем в планировщик
        success = warming_scheduler.add_job(domain_id, job.id, schedule)
        
        if success:
            group_desc = url_grouper.get_group_description(group)
            
            await callback.message.edit_text(
                f"✅ <b>Расписание установлено!</b>\n\n"
                f"🌐 Домен: <b>{domain.name}</b>\n"
                f"📊 Группа: {group_desc}\n"
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


@router.callback_query(F.data.startswith("schedule_group_"))
async def callback_schedule_group(callback: CallbackQuery):
    """Выбор частоты после выбора группы"""
    await callback.answer()
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    group = int(parts[3])
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    group_desc = url_grouper.get_group_description(group)
    
    await callback.message.edit_text(
        f"⏰ <b>Настройка расписания для {domain.name}</b>\n\n"
        f"📊 Группа: {group_desc}\n\n"
        f"Выберите частоту прогрева:",
        parse_mode="HTML",
        reply_markup=get_schedule_keyboard(domain_id, group)
    )


@router.callback_query(F.data.startswith("schedule_"))
async def callback_schedule(callback: CallbackQuery):
    """Показать выбор группы для настройки расписания"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[1])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.message.edit_text("❌ Домен не найден.")
        return
    
    # Получаем статистику по группам
    all_urls = [url.url for url in domain.urls]
    stats = url_grouper.get_group_stats(all_urls, domain.name)
    
    await callback.message.edit_text(
        f"⏰ <b>Настройка расписания</b>\n\n"
        f"🌐 Домен: <b>{domain.name}</b>\n\n"
        f"Сначала выберите группу URL:\n"
        f"🏠 Группа 1: <b>{stats[1]}</b> страниц (только главная)\n"
        f"📄 Группа 2: <b>{stats[2]}</b> страниц (основные)\n"
        f"🌐 Группа 3: <b>{stats[3]}</b> страниц (все)",
        parse_mode="HTML",
        reply_markup=get_warming_group_keyboard(domain_id, action="schedule")
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


@router.callback_query(F.data.startswith("stats_"))
async def callback_stats(callback: CallbackQuery):
    """Показать выбор периода статистики"""
    domain_id = int(callback.data.split("_")[1])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.answer("❌ Домен не найден", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"📊 <b>Статистика для {domain.name}</b>\n\n"
        f"Выберите период:",
        parse_mode="HTML",
        reply_markup=get_stats_period_keyboard(domain_id)
    )


@router.callback_query(F.data.startswith("show_stats_"))
async def callback_show_stats(callback: CallbackQuery):
    """Показать график статистики"""
    await callback.answer("📊 Генерирую график...")
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    period = parts[3]
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain:
        await callback.answer("❌ Домен не найден", show_alert=True)
        return
    
    try:
        # Определяем период
        if period == "24h":
            start_date = datetime.utcnow() - timedelta(hours=24)
            period_name = "за последние 24 часа"
        elif period == "7d":
            start_date = datetime.utcnow() - timedelta(days=7)
            period_name = "за последние 7 дней"
        elif period == "30d":
            start_date = datetime.utcnow() - timedelta(days=30)
            period_name = "за последние 30 дней"
        else:  # all
            start_date = datetime.utcnow() - timedelta(days=365)  # год назад
            period_name = "за всю историю"
        
        # Получаем историю прогревов
        history = await db_manager.get_warming_history_by_period(
            domain_id=domain_id,
            start_date=start_date,
            end_date=datetime.utcnow()
        )
        
        if not history:
            await callback.message.edit_text(
                f"📊 <b>Статистика для {domain.name}</b>\n\n"
                f"❌ Нет данных {period_name}.\n\n"
                f"Выполните хотя бы один прогрев, чтобы увидеть статистику.",
                parse_mode="HTML",
                reply_markup=get_stats_period_keyboard(domain_id)
            )
            return
        
        # Генерируем график
        graph_buf = graph_generator.generate_combined_graph(history, domain.name)
        
        if not graph_buf:
            await callback.message.edit_text(
                f"❌ Ошибка генерации графика.\n\n"
                f"Попробуйте позже.",
                reply_markup=get_stats_period_keyboard(domain_id)
            )
            return
        
        # Формируем текстовую статистику
        avg_time = sum(h.avg_response_time for h in history) / len(history)
        avg_success_rate = sum(
            (h.successful_requests / h.total_requests * 100) if h.total_requests > 0 else 0
            for h in history
        ) / len(history)
        
        stats_text = (
            f"📊 <b>Статистика для {domain.name}</b>\n"
            f"{period_name}\n\n"
            f"📈 <b>Показатели:</b>\n"
            f"• Всего измерений: <b>{len(history)}</b>\n"
            f"• Средняя скорость: <b>{avg_time:.2f}s</b>\n"
            f"• Средняя успешность: <b>{avg_success_rate:.1f}%</b>\n\n"
            f"📊 График прикреплен ниже"
        )
        
        # Удаляем старое сообщение
        await callback.message.delete()
        
        # Отправляем новое сообщение с графиком
        photo = BufferedInputFile(graph_buf.read(), filename=f"stats_{domain.name}_{period}.png")
        await callback.message.answer_photo(
            photo=photo,
            caption=stats_text,
            parse_mode="HTML",
            reply_markup=get_stats_period_keyboard(domain_id)
        )
        
        logger.info(f"Sent statistics graph for {domain.name} (period: {period})")
        
    except Exception as e:
        logger.error(f"Error showing statistics for domain {domain_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при получении статистики: {str(e)}",
            reply_markup=get_stats_period_keyboard(domain_id)
        )
