"""
Модуль для генерации и отправки отчетов
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.core.db import db_manager
from app.models.domain import User, Domain, WarmingHistory

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Генератор отчетов"""
    
    async def generate_admin_report(self) -> str:
        """Генерация общего отчета для администраторов"""
        # Получаем все домены
        domains = await db_manager.get_all_domains()
        
        if not domains:
            return (
                "📊 <b>Ежедневный отчет</b>\n\n"
                "Нет доменов для мониторинга."
            )
        
        # Период за последние сутки
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        total_domains = len(domains)
        total_urls = sum(len(domain.urls) for domain in domains)
        
        # Статистика по прогревам
        total_warmings = 0
        total_requests = 0
        total_success = 0
        total_errors = 0
        avg_times = []
        
        for domain in domains:
            history = await db_manager.get_warming_history_by_period(
                domain.id, start_time, end_time
            )
            
            total_warmings += len(history)
            for h in history:
                total_requests += h.total_requests
                total_success += h.successful_requests
                total_errors += h.failed_requests + h.timeout_requests
                avg_times.append(h.avg_response_time)
        
        overall_avg_time = sum(avg_times) / len(avg_times) if avg_times else 0
        success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0
        
        report = (
            f"📊 <b>Ежедневный отчет для администраторов</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"🌐 <b>Домены:</b> {total_domains}\n"
            f"📄 <b>Всего страниц:</b> {total_urls}\n\n"
            f"🔥 <b>Прогревов за сутки:</b> {total_warmings}\n"
            f"📊 <b>Всего запросов:</b> {total_requests}\n"
            f"✅ <b>Успешных:</b> {total_success} ({success_rate:.1f}%)\n"
            f"❌ <b>Ошибок:</b> {total_errors}\n\n"
            f"⏱ <b>Среднее время ответа:</b> {overall_avg_time:.2f}с"
        )
        
        # Домены с проблемами
        problem_domains = []
        for domain in domains:
            history = await db_manager.get_warming_history_by_period(
                domain.id, start_time, end_time
            )
            
            if history:
                latest = history[-1] if history else None
                if latest and latest.avg_response_time > 3.0:  # Медленные домены
                    problem_domains.append((domain.name, latest.avg_response_time))
        
        if problem_domains:
            report += "\n\n⚠️ <b>Медленные домены:</b>\n"
            for name, avg_time in problem_domains[:5]:
                report += f"• {name}: {avg_time:.2f}с\n"
        
        return report
    
    async def generate_client_report(self, client_id: int) -> str:
        """Генерация отчета для клиента"""
        # Получаем домены клиента
        domains = await db_manager.get_domains_by_client(client_id)
        
        if not domains:
            return (
                "📊 <b>Ваш ежедневный отчет</b>\n\n"
                "У вас пока нет доменов в мониторинге."
            )
        
        # Период за последние сутки
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        
        total_urls = sum(len(domain.urls) for domain in domains)
        
        # Статистика по каждому домену
        domain_stats = []
        
        for domain in domains:
            history = await db_manager.get_warming_history_by_period(
                domain.id, start_time, end_time
            )
            
            if history:
                avg_times = [h.avg_response_time for h in history]
                avg_time = sum(avg_times) / len(avg_times) if avg_times else 0
                
                total_reqs = sum(h.total_requests for h in history)
                total_success = sum(h.successful_requests for h in history)
                success_rate = (total_success / total_reqs * 100) if total_reqs > 0 else 0
                
                domain_stats.append({
                    'name': domain.name,
                    'urls': len(domain.urls),
                    'avg_time': avg_time,
                    'success_rate': success_rate,
                    'checks': len(history)
                })
            else:
                domain_stats.append({
                    'name': domain.name,
                    'urls': len(domain.urls),
                    'avg_time': 0,
                    'success_rate': 0,
                    'checks': 0
                })
        
        # Формируем отчет для клиентов (без упоминания "прогрева")
        report = (
            f"📊 <b>Утренний отчет по вашим сайтам</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"🌐 <b>Доменов в мониторинге:</b> {len(domains)}\n"
            f"📄 <b>Всего страниц:</b> {total_urls}\n\n"
        )
        
        for stat in domain_stats:
            # Определяем статус по скорости
            if stat['avg_time'] == 0:
                status_emoji = "🔵"
                status_text = "Готовится к запуску"
            elif stat['avg_time'] < 2.0:
                status_emoji = "✅"
                status_text = "Отлично"
            elif stat['avg_time'] < 4.0:
                status_emoji = "⚠️"
                status_text = "Нормально"
            else:
                status_emoji = "❌"
                status_text = "Медленно"
            
            report += (
                f"{status_emoji} <b>{stat['name']}</b>\n"
                f"   Статус: {status_text}\n"
                f"   📄 Страниц: {stat['urls']}\n"
                f"   ⏱ Среднее время загрузки: {stat['avg_time']:.2f}с\n"
                f"   ✅ Доступность: {stat['success_rate']:.1f}%\n\n"
            )
        
        report += "\n💡 <i>Ваши сайты работают в оптимальном режиме</i>"
        
        return report
    
    async def send_daily_reports(self, bot):
        """Отправка ежедневных отчетов всем пользователям"""
        try:
            # Отправляем отчет администраторам
            admins = await db_manager.get_all_admins()
            admin_report = await self.generate_admin_report()
            
            for admin in admins:
                try:
                    await bot.send_message(admin.id, admin_report, parse_mode="HTML")
                    logger.info(f"Sent daily report to admin {admin.id}")
                except Exception as e:
                    logger.error(f"Failed to send report to admin {admin.id}: {e}")
            
            # Отправляем отчеты клиентам
            clients = await db_manager.get_all_clients()
            
            for client in clients:
                try:
                    client_report = await self.generate_client_report(client.id)
                    await bot.send_message(client.id, client_report, parse_mode="HTML")
                    logger.info(f"Sent daily report to client {client.id}")
                except Exception as e:
                    logger.error(f"Failed to send report to client {client.id}: {e}")
            
            logger.info("Daily reports sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending daily reports: {e}", exc_info=True)
    
    async def send_error_notification(self, bot, domain_name: str, error_message: str):
        """Отправка уведомления об ошибке администраторам"""
        try:
            admins = await db_manager.get_all_admins()
            
            message = (
                f"❌ <b>Ошибка прогрева</b>\n\n"
                f"🌐 Домен: <b>{domain_name}</b>\n"
                f"⚠️ Ошибка: {error_message}\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
            
            for admin in admins:
                try:
                    await bot.send_message(admin.id, message, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Failed to send error notification to admin {admin.id}: {e}")
            
        except Exception as e:
            logger.error(f"Error sending error notification: {e}", exc_info=True)


# Глобальный экземпляр
report_generator = ReportGenerator()

