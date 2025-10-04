"""
Планировщик задач прогрева
"""
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.db import db_manager
from app.core.warmer import warmer

logger = logging.getLogger(__name__)


class WarmingScheduler:
    """Планировщик задач прогрева"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_map: Dict[int, str] = {}  # domain_id -> apscheduler_job_id
    
    def start(self) -> None:
        """Запуск планировщика"""
        self.scheduler.start()
        logger.info("Scheduler started")
    
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
            
            # Прогреваем
            urls = [url.url for url in domain.urls]
            stats = await warmer.warm_site(urls)
            
            # Обновляем время последнего запуска
            await db_manager.update_job_last_run(job_id)
            
            logger.info(f"✅ Scheduled warming completed for {domain.name}: {stats}")
            
        except Exception as e:
            logger.error(f"Error in scheduled warming task for domain {domain_id}: {e}", exc_info=True)
    
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


# Глобальный экземпляр
warming_scheduler = WarmingScheduler()

