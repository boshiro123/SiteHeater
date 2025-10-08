"""
Менеджер задач прогрева для параллельного выполнения
"""
import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from app.core.warmer import warmer
from app.core.db import db_manager

logger = logging.getLogger(__name__)


class WarmingManager:
    """Менеджер для параллельного выполнения задач прогрева"""
    
    def __init__(self):
        self.active_tasks: Dict[int, asyncio.Task] = {}  # domain_id -> Task
        self.task_info: Dict[int, Dict[str, Any]] = {}  # domain_id -> info
    
    def is_warming(self, domain_id: int) -> bool:
        """Проверка, идет ли прогрев домена"""
        if domain_id in self.active_tasks:
            task = self.active_tasks[domain_id]
            return not task.done()
        return False
    
    def get_active_count(self) -> int:
        """Получение количества активных прогревов"""
        # Очищаем завершенные задачи
        self._cleanup_completed_tasks()
        return len(self.active_tasks)
    
    def _cleanup_completed_tasks(self):
        """Очистка завершенных задач"""
        completed = [
            domain_id for domain_id, task in self.active_tasks.items()
            if task.done()
        ]
        for domain_id in completed:
            del self.active_tasks[domain_id]
            if domain_id in self.task_info:
                del self.task_info[domain_id]
    
    async def start_warming(
        self,
        domain_id: int,
        domain_name: str,
        urls: list,
        user_id: Optional[int] = None,
        bot=None
    ) -> bool:
        """
        Запуск прогрева домена в фоновом режиме
        
        Args:
            domain_id: ID домена
            domain_name: Имя домена
            urls: Список URL для прогрева
            user_id: ID пользователя, запустившего прогрев (для уведомления)
            bot: Экземпляр бота для отправки уведомлений
        
        Returns:
            True если прогрев запущен, False если уже идет
        """
        # Проверяем, не идет ли уже прогрев этого домена
        if self.is_warming(domain_id):
            logger.warning(f"Domain {domain_name} is already being warmed")
            return False
        
        # Создаем задачу прогрева
        task = asyncio.create_task(
            self._warm_domain_task(domain_id, domain_name, urls, user_id, bot)
        )
        
        self.active_tasks[domain_id] = task
        self.task_info[domain_id] = {
            "domain_name": domain_name,
            "start_time": datetime.utcnow(),
            "user_id": user_id,
            "urls_count": len(urls)
        }
        
        logger.info(f"🚀 Started warming task for {domain_name} (domain_id={domain_id})")
        return True
    
    async def _warm_domain_task(
        self,
        domain_id: int,
        domain_name: str,
        urls: list,
        user_id: Optional[int],
        bot
    ):
        """Фоновая задача прогрева домена"""
        try:
            logger.info(f"🔥 Warming {domain_name} ({len(urls)} URLs)")
            
            # Выполняем прогрев (передаем имя домена для логирования)
            stats = await warmer.warm_site(urls, domain_name=domain_name)
            
            # Формируем отчет
            success_rate = (stats["success"] / stats["total_requests"] * 100) if stats["total_requests"] > 0 else 0
            
            # Определяем эмодзи
            if success_rate >= 90:
                status_emoji = "✅"
            elif success_rate >= 70:
                status_emoji = "⚠️"
            else:
                status_emoji = "❌"
            
            message = (
                f"{status_emoji} <b>Прогрев завершен</b>\n\n"
                f"🌐 Домен: <b>{domain_name}</b>\n"
                f"🕒 Время: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                f"📊 <b>Статистика:</b>\n"
                f"• Всего запросов: <b>{stats['total_requests']}</b>\n"
                f"• ✅ Успешно: <b>{stats['success']}</b> ({success_rate:.1f}%)\n"
                f"• ⏱ Таймауты: <b>{stats['timeout']}</b>\n"
                f"• ❌ Ошибки: <b>{stats['error']}</b>\n"
                f"• ⏱ Среднее время: <b>{stats['avg_time']:.2f}s</b>\n"
                f"• ⏱ Общее время: <b>{stats['total_time']:.2f}s</b>"
            )
            
            # Отправляем уведомление пользователю, запустившему прогрев
            if bot and user_id:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending notification to user {user_id}: {e}")
            
            logger.info(f"✅ Completed warming {domain_name}: {stats}")
            
        except Exception as e:
            logger.error(f"❌ Error warming {domain_name}: {e}", exc_info=True)
            
            # Отправляем уведомление об ошибке
            if bot and user_id:
                try:
                    error_message = (
                        f"❌ <b>Ошибка прогрева</b>\n\n"
                        f"🌐 Домен: <b>{domain_name}</b>\n"
                        f"⚠️ Ошибка: {str(e)}"
                    )
                    await bot.send_message(
                        chat_id=user_id,
                        text=error_message,
                        parse_mode="HTML"
                    )
                except Exception as send_error:
                    logger.error(f"Error sending error notification: {send_error}")
        
        finally:
            # Задача завершена, она будет удалена при следующей очистке
            pass
    
    async def stop_warming(self, domain_id: int) -> bool:
        """
        Остановка прогрева домена
        
        Args:
            domain_id: ID домена
        
        Returns:
            True если прогрев был остановлен, False если не был запущен
        """
        if domain_id not in self.active_tasks:
            return False
        
        task = self.active_tasks[domain_id]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"⏹ Stopped warming for domain_id={domain_id}")
        
        del self.active_tasks[domain_id]
        if domain_id in self.task_info:
            del self.task_info[domain_id]
        
        return True
    
    def get_warming_info(self, domain_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о прогреве домена"""
        if domain_id not in self.task_info:
            return None
        
        info = self.task_info[domain_id].copy()
        info["is_active"] = self.is_warming(domain_id)
        
        if info["is_active"]:
            elapsed = (datetime.utcnow() - info["start_time"]).total_seconds()
            info["elapsed_seconds"] = elapsed
        
        return info
    
    async def stop_all(self):
        """Остановка всех прогревов"""
        logger.info("Stopping all warming tasks...")
        
        for domain_id in list(self.active_tasks.keys()):
            await self.stop_warming(domain_id)
        
        logger.info("All warming tasks stopped")


# Глобальный экземпляр
warming_manager = WarmingManager()

