"""
Планировщик задач прогрева
"""
import asyncio
import logging
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import config
from app.core.db import db_manager
from app.core.warmer import warmer
from app.core.reports import report_generator
from app.utils.url_grouper import url_grouper
from app.utils.sitemap import sitemap_parser

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


class WarmingScheduler:
    """Планировщик задач прогрева"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_map: Dict[int, str] = {}  # domain_id -> apscheduler_job_id
        self.bot: Optional['Bot'] = None
    
    def set_bot(self, bot: 'Bot') -> None:
        """Установка экземпляра бота для отправки уведомлений"""
        self.bot = bot
        logger.info("Bot instance set for scheduler")
    
    def start(self) -> None:
        """Запуск планировщика"""
        self.scheduler.start()
        
        # Добавляем задачу для ежедневных отчетов (в 6:00 UTC = 9:00 UTC+3 Минск)
        self.scheduler.add_job(
            self.send_daily_reports_task,
            trigger='cron',
            hour=6,
            minute=0,
            id='daily_reports',
            replace_existing=True
        )
        
        # Добавляем задачу для обновления URL (в 3:00 UTC = 6:00 UTC+3 Минск - ночью)
        self.scheduler.add_job(
            self.update_domains_urls_task,
            trigger='cron',
            hour=3,
            minute=0,
            id='update_urls',
            replace_existing=True
        )
        
        logger.info("Scheduler started with daily reports at 06:00 UTC and URL updates at 03:00 UTC")

    
    def shutdown(self) -> None:
        """Остановка планировщика"""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")
    
    def parse_schedule(self, schedule: str) -> Optional[Dict]:
        """
        Парсинг строки расписания
        Формат: "5m", "1h", "30m" и т.д.
        Возвращает параметры для IntervalTrigger
        """
        if not schedule:
            return None
        
        schedule = schedule.strip().lower()
        
        try:
            if schedule.endswith('m'):
                minutes = int(schedule[:-1])
                return {"minutes": minutes}
            elif schedule.endswith('h'):
                hours = int(schedule[:-1])
                return {"hours": hours}
            elif schedule.endswith('s'):
                seconds = int(schedule[:-1])
                return {"seconds": seconds}
            else:
                # По умолчанию считаем минуты
                minutes = int(schedule)
                return {"minutes": minutes}
        except ValueError:
            logger.error(f"Invalid schedule format: {schedule}")
            return None
    
    async def warm_domain_task(self, domain_id: int, job_id: int) -> None:
        """Задача прогрева домена"""
        try:
            logger.info(f"⏰ Scheduled warming task for domain_id={domain_id}")
            
            # Получаем домен с URL
            domain = await db_manager.get_domain_by_id(domain_id)
            
            if not domain or not domain.is_active:
                logger.warning(f"Domain {domain_id} not found or inactive, removing job")
                self.remove_job(domain_id)
                return
            
            if not domain.urls:
                logger.warning(f"No URLs for domain {domain_id}")
                return
            
            # Получаем Job для определения группы
            result = await db_manager.get_active_jobs()
            current_job = next((j for j in result if j.id == job_id), None)
            
            # Используем группу из Job (для автопрогрева)
            active_group = current_job.active_url_group if current_job else 3
            
            # Фильтруем URL по группе из Job
            all_urls = [url.url for url in domain.urls]
            urls = url_grouper.filter_urls_by_group(all_urls, domain.name, active_group)
            
            logger.info(f"Scheduled warming for {domain.name} (group {active_group}): {len(urls)}/{len(all_urls)} URLs")
            
            # Прогреваем (передаем имя домена для логирования)
            stats = await warmer.warm_site(urls, domain_name=domain.name)
            
            # Сохраняем результаты прогрева в БД
            try:
                await db_manager.save_warming_result(
                    domain_id=domain_id,
                    started_at=stats["started_at"],
                    completed_at=stats["completed_at"],
                    total_requests=stats["total_requests"],
                    successful_requests=stats["success"],
                    failed_requests=stats["error"],
                    timeout_requests=stats["timeout"],
                    avg_response_time=stats["avg_time"],
                    min_response_time=stats["min_time"],
                    max_response_time=stats["max_time"],
                    warming_type="scheduled"
                )
                logger.info(f"💾 Saved warming result to database for {domain.name}")
            except Exception as e:
                logger.error(f"Error saving warming result to DB: {e}", exc_info=True)
            
            # Обновляем время последнего запуска
            await db_manager.update_job_last_run(job_id)
            
            logger.info(f"✅ Scheduled warming completed for {domain.name}: {stats}")
            
            # Отправляем уведомление пользователю (если включено в настройках)
            if config.SEND_WARMING_NOTIFICATIONS and self.bot:
                await self._send_warming_notification(domain, stats)
            
        except Exception as e:
            logger.error(f"Error in scheduled warming task for domain {domain_id}: {e}", exc_info=True)
    
    async def _send_warming_notification(self, domain, stats: Dict) -> None:
        """Отправка уведомления о прогреве (только если включено в настройках)"""
        
        # Проверяем, включены ли уведомления
        if not config.SEND_WARMING_NOTIFICATIONS:
            logger.debug(f"Warming notifications disabled, skipping for domain {domain.name}")
            return
        
        try:
            success_rate = (stats["success"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0
            
            # Определяем эмодзи в зависимости от успешности
            if success_rate >= 90:
                status_emoji = "✅"
            elif success_rate >= 70:
                status_emoji = "⚠️"
            else:
                status_emoji = "❌"
            
            # 3. Убрать "общее время" из отчета
            message = (
                f"{status_emoji} <b>Автопрогрев завершен</b>\n\n"
                f"🌐 Домен: <b>{domain.name}</b>\n"
                f"🕒 Время: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Всего запросов: <b>{stats['total_requests']}</b>\n"
                f"• ✅ Успешно: <b>{stats['success']}</b> ({success_rate:.1f}%)\n"
                f"• ⏱ Таймауты: <b>{stats['timeout']}</b>\n"
                f"• ❌ Ошибки: <b>{stats['error']}</b>\n"
                f"• ⏱ Среднее время: <b>{stats['avg_time']:.2f}s</b>"
            )
            
            # Если указан технический канал - отправляем туда
            if config.TECHNICAL_CHANNEL_ID:
                try:
                    logger.debug(f"Attempting to send notification to channel: {config.TECHNICAL_CHANNEL_ID}")
                    await self.bot.send_message(
                        chat_id=config.TECHNICAL_CHANNEL_ID,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(f"📤 Notification sent to technical channel ({config.TECHNICAL_CHANNEL_ID}) for domain {domain.name}")
                except Exception as e:
                    logger.error(
                        f"❌ Failed to send notification to technical channel ({config.TECHNICAL_CHANNEL_ID}): {type(e).__name__}: {e}\n"
                        f"Проверьте:\n"
                        f"1. Бот добавлен в канал как администратор\n"
                        f"2. У бота есть право 'Публиковать сообщения'\n"
                        f"3. ID канала указан правильно (начинается с -100)",
                        exc_info=True
                    )
            else:
                # Иначе отправляем администраторам (старое поведение)
                admins = await db_manager.get_all_admins()
                
                sent_count = 0
                for admin in admins:
                    try:
                        await self.bot.send_message(
                            chat_id=admin.id,
                            text=message,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to send notification to admin {admin.id}: {e}")
                
                logger.info(f"📤 Notification sent to {sent_count}/{len(admins)} admins for domain {domain.name}")
            
        except Exception as e:
            logger.error(f"Error sending notifications: {e}", exc_info=True)
    
    def add_job(self, domain_id: int, job_id: int, schedule: str) -> bool:
        """Добавление задачи в планировщик"""
        try:
            # Удаляем старую задачу, если есть
            self.remove_job(domain_id)
            
            # Парсим расписание
            interval_params = self.parse_schedule(schedule)
            
            if not interval_params:
                logger.error(f"Failed to parse schedule: {schedule}")
                return False
            
            # Добавляем задачу
            trigger = IntervalTrigger(**interval_params)
            
            apscheduler_job = self.scheduler.add_job(
                self.warm_domain_task,
                trigger=trigger,
                args=[domain_id, job_id],
                id=f"warm_domain_{domain_id}",
                replace_existing=True,
            )
            
            self.job_map[domain_id] = apscheduler_job.id
            
            logger.info(f"✅ Added scheduled job for domain {domain_id}: {schedule}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding job for domain {domain_id}: {e}", exc_info=True)
            return False
    
    def remove_job(self, domain_id: int) -> bool:
        """Удаление задачи из планировщика"""
        try:
            if domain_id in self.job_map:
                job_id = self.job_map[domain_id]
                self.scheduler.remove_job(job_id)
                del self.job_map[domain_id]
                logger.info(f"✅ Removed scheduled job for domain {domain_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing job for domain {domain_id}: {e}")
            return False
    
    async def reload_jobs(self) -> None:
        """Перезагрузка всех активных задач из базы"""
        logger.info("Reloading scheduled jobs from database...")
        
        try:
            active_jobs = await db_manager.get_active_jobs()
            
            # Очищаем все текущие задачи
            for domain_id in list(self.job_map.keys()):
                self.remove_job(domain_id)
            
            # Добавляем активные задачи
            for job in active_jobs:
                if job.schedule:
                    self.add_job(job.domain_id, job.id, job.schedule)
            
            logger.info(f"✅ Reloaded {len(active_jobs)} scheduled jobs")
            
        except Exception as e:
            logger.error(f"Error reloading jobs: {e}", exc_info=True)
    
    async def send_daily_reports_task(self) -> None:
        """Задача для отправки ежедневных отчетов"""
        if not self.bot:
            logger.warning("Bot instance not set, skipping daily reports")
            return
        
        logger.info("Sending daily reports...")
        await report_generator.send_daily_reports(self.bot)
    
    async def update_domains_urls_task(self) -> None:
        """Задача для автоматического обновления URL всех доменов"""
        logger.info("🔄 Starting automatic URL update for all domains...")
        
        try:
            # Получаем все активные домены
            domains = await db_manager.get_all_domains()
            
            if not domains:
                logger.info("No domains to update")
                return
            
            updated_count = 0
            errors_count = 0
            
            for domain in domains:
                try:
                    logger.info(f"Updating URLs for domain: {domain.name}")
                    
                    # Получаем новые URL
                    new_urls = await sitemap_parser.discover_urls(domain.name)
                    
                    if not new_urls:
                        logger.warning(f"No URLs found for {domain.name}")
                        continue
                    
                    # Получаем старые URL
                    old_urls = set(url.url for url in domain.urls)
                    new_urls_set = set(new_urls)
                    
                    # Находим новые URL (которых не было раньше)
                    added_urls = new_urls_set - old_urls
                    # Находим удаленные URL (которые были, но больше нет)
                    removed_urls = old_urls - new_urls_set
                    
                    # Удаляем старые URL
                    if removed_urls:
                        await db_manager.delete_urls_by_domain(domain.id, list(removed_urls))
                        logger.info(f"Removed {len(removed_urls)} URLs from {domain.name}")
                    
                    # Добавляем новые URL
                    if added_urls:
                        await db_manager.add_urls_to_domain(domain.id, list(added_urls))
                        logger.info(f"Added {len(added_urls)} new URLs to {domain.name}")
                    
                    updated_count += 1
                    
                    # Отправляем уведомление админам если были значительные изменения
                    if self.bot and (len(added_urls) > 10 or len(removed_urls) > 10):
                        admins = await db_manager.get_all_admins()
                        
                        message = (
                            f"📊 <b>Обновление URL</b>\n\n"
                            f"🌐 Домен: <b>{domain.name}</b>\n"
                            f"➕ Добавлено: <b>{len(added_urls)}</b> URL\n"
                            f"➖ Удалено: <b>{len(removed_urls)}</b> URL\n"
                            f"📄 Всего: <b>{len(new_urls_set)}</b> URL"
                        )
                        
                        for admin in admins:
                            try:
                                await self.bot.send_message(admin.id, message, parse_mode="HTML")
                            except Exception as e:
                                logger.warning(f"Failed to send update notification to admin {admin.id}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error updating URLs for domain {domain.name}: {e}", exc_info=True)
                    errors_count += 1
            
            logger.info(f"✅ URL update completed: {updated_count} domains updated, {errors_count} errors")
            
        except Exception as e:
            logger.error(f"Error in URL update task: {e}", exc_info=True)


# Глобальный экземпляр
warming_scheduler = WarmingScheduler()

