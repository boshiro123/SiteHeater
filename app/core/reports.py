"""
Модуль для генерации и отправки отчетов
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.core.db import db_manager
from app.models.domain import User, Domain, WarmingHistory
from app.utils.url_grouper import url_grouper

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
        
        # Получаем активные задачи для определения количества URL в прогреве
        active_jobs = await db_manager.get_active_jobs()
        job_map = {job.domain_id: job for job in active_jobs}
        
        total_domains = len(domains)
        total_urls = 0  # Реально прогреваемые URL
        
        # Статистика по прогревам
        total_warmings = 0
        total_requests = 0
        total_success = 0
        total_errors = 0
        avg_times = []
        
        # Детальная статистика по каждому домену
        domain_stats = []
        
        for domain in domains:
            history = await db_manager.get_warming_history_by_period(
                domain.id, start_time, end_time
            )
            
            # Получаем Job для домена чтобы узнать active_url_group
            job = job_map.get(domain.id)
            
            # Определяем реальное количество URL в прогреве
            all_urls = [url.url for url in domain.urls]
            if job and job.active_url_group:
                # Фильтруем URL по группе
                warming_urls = url_grouper.filter_urls_by_group(all_urls, domain.name, job.active_url_group)
                url_count = len(warming_urls)
            else:
                # Если нет Job - значит все URL
                url_count = len(all_urls)
            
            total_urls += url_count
            
            # Статистика по домену
            domain_warmings = len(history)
            domain_requests = 0
            domain_success = 0
            domain_errors = 0
            domain_avg_times = []
            
            for h in history:
                domain_requests += h.total_requests
                domain_success += h.successful_requests
                domain_errors += h.failed_requests + h.timeout_requests
                domain_avg_times.append(h.avg_response_time)
            
            domain_avg_time = sum(domain_avg_times) / len(domain_avg_times) if domain_avg_times else 0
            
            domain_stats.append({
                'name': domain.name,
                'url_count': url_count,
                'avg_time': domain_avg_time,
                'warmings': domain_warmings,
                'requests': domain_requests,
                'success': domain_success,
                'errors': domain_errors
            })
            
            # Общая статистика
            total_warmings += domain_warmings
            total_requests += domain_requests
            total_success += domain_success
            total_errors += domain_errors
            if domain_avg_times:
                avg_times.extend(domain_avg_times)
        
        overall_avg_time = sum(avg_times) / len(avg_times) if avg_times else 0
        success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0
        
        # Вычисляем среднее количество запросов в минуту за сутки
        total_minutes = 1440  # 24 часа = 1440 минут
        avg_requests_per_minute = total_requests / total_minutes if total_requests > 0 else 0
        
        report = (
            f"📊 <b>Ежедневный отчет для администраторов</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"🌐 <b>Домены:</b> {total_domains}\n"
            f"📄 <b>Страниц в работе:</b> {total_urls}\n\n"
            f"🔥 <b>Прогревов за сутки:</b> {total_warmings}\n"
            f"📊 <b>Всего запросов:</b> {total_requests}\n"
            f"⚡️ <b>Среднее запросов/мин:</b> {avg_requests_per_minute:.2f}\n"
            f"✅ <b>Успешных:</b> {total_success} ({success_rate:.1f}%)\n"
            f"❌ <b>Ошибок:</b> {total_errors}\n\n"
            f"⏱ <b>Среднее время ответа:</b> {overall_avg_time:.2f}с\n\n"
        )
        
        # Добавляем детальную информацию по каждому домену
        if domain_stats:
            report += "📋 <b>Статистика по доменам:</b>\n\n"
            for stat in domain_stats:
                # Определяем эмодзи статуса
                if stat['avg_time'] == 0:
                    status = "🔵"
                elif stat['avg_time'] < 2.0:
                    status = "✅"
                elif stat['avg_time'] < 4.0:
                    status = "⚠️"
                else:
                    status = "❌"
                
                # Компактный формат в одну строку
                report += (
                    f"{status} <b>{stat['name']}</b>\n"
                    f"   {stat['avg_time']:.2f}с • {stat['url_count']} стр • "
                    f"{stat['warmings']} прогр • {stat['requests']} запр • "
                    f"✅{stat['success']} • ❌{stat['errors']}\n\n"
                )
        
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
        
        # Получаем все активные задачи для определения количества URL в прогреве
        active_jobs = await db_manager.get_active_jobs()
        job_map = {job.domain_id: job for job in active_jobs}
        
        total_urls = 0  # Будем считать реально прогреваемые URL
        
        # Статистика по каждому домену
        domain_stats = []
        
        for domain in domains:
            # Получаем Job для домена чтобы узнать active_url_group
            job = job_map.get(domain.id)
            
            # Определяем реальное количество URL в прогреве
            all_urls = [url.url for url in domain.urls]
            if job and job.active_url_group:
                # Фильтруем URL по группе
                warming_urls = url_grouper.filter_urls_by_group(all_urls, domain.name, job.active_url_group)
                url_count = len(warming_urls)
            else:
                # Если нет Job - значит все URL
                url_count = len(all_urls)
            
            total_urls += url_count
            
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
                    'urls': url_count,  # Реальное количество в прогреве
                    'avg_time': avg_time,
                    'success_rate': success_rate,
                    'checks': len(history)
                })
            else:
                domain_stats.append({
                    'name': domain.name,
                    'urls': url_count,  # Реальное количество в прогреве
                    'avg_time': 0,
                    'success_rate': 0,
                    'checks': 0
                })
        
        # Формируем отчет для клиентов (без упоминания "прогрева")
        report = (
            f"📊 <b>Утренний отчет по вашим сайтам</b>\n"
            f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"🌐 <b>Доменов в мониторинге:</b> {len(domains)}\n"
            f"📄 <b>Страниц в работе:</b> {total_urls}\n\n"
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
                f"   📄 Страниц в работе: {stat['urls']}\n"
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
    
    async def generate_hourly_admin_report(self) -> str:
        """Генерация 2-часового отчета для администраторов"""
        # Период за последние 2 часа
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=2)
        
        # Получаем все домены
        domains = await db_manager.get_all_domains()
        
        if not domains:
            return (
                "📊 <b>2-часовой отчет</b>\n"
                f"🕐 {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n\n"
                "Нет доменов для мониторинга."
            )
        
        total_requests = 0
        total_warmings = 0
        total_success = 0
        total_errors = 0
        
        # Статистика по каждому домену
        domain_stats = []
        
        for domain in domains:
            history = await db_manager.get_warming_history_by_period(
                domain.id, start_time, end_time
            )
            
            if history:
                domain_warmings = len(history)
                domain_requests = sum(h.total_requests for h in history)
                domain_success = sum(h.successful_requests for h in history)
                domain_errors = sum(h.failed_requests + h.timeout_requests for h in history)
                
                total_warmings += domain_warmings
                total_requests += domain_requests
                total_success += domain_success
                total_errors += domain_errors
                
                domain_stats.append({
                    'name': domain.name,
                    'warmings': domain_warmings,
                    'requests': domain_requests,
                    'success': domain_success,
                    'errors': domain_errors
                })
        
        # Вычисляем среднее количество запросов в минуту
        total_minutes = 120  # 2 часа = 120 минут
        avg_requests_per_minute = total_requests / total_minutes if total_requests > 0 else 0
        success_rate = (total_success / total_requests * 100) if total_requests > 0 else 0
        
        report = (
            f"📊 <b>2-часовой отчет</b>\n"
            f"🕐 {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n\n"
            f"🔥 <b>Прогревов:</b> {total_warmings}\n"
            f"📊 <b>Всего запросов:</b> {total_requests}\n"
            f"⚡️ <b>Среднее запросов/мин:</b> {avg_requests_per_minute:.2f}\n"
            f"✅ <b>Успешных:</b> {total_success} ({success_rate:.1f}%)\n"
            f"❌ <b>Ошибок:</b> {total_errors}\n"
        )
        
        # Добавляем детали по доменам, если были прогревы
        if domain_stats:
            report += "\n📋 <b>Детали:</b>\n"
            for stat in domain_stats:
                report += (
                    f"• <b>{stat['name']}</b>: "
                    f"{stat['warmings']} прогр, "
                    f"{stat['requests']} запр, "
                    f"✅{stat['success']} ❌{stat['errors']}\n"
                )
        
        return report
    
    async def send_hourly_admin_reports(self, bot):
        """Отправка 2-часовых отчетов администраторам"""
        try:
            admins = await db_manager.get_all_admins()
            report = await self.generate_hourly_admin_report()
            
            for admin in admins:
                try:
                    await bot.send_message(admin.id, report, parse_mode="HTML")
                    logger.info(f"Sent 2-hour report to admin {admin.id}")
                except Exception as e:
                    logger.error(f"Failed to send 2-hour report to admin {admin.id}: {e}")
            
            logger.info("2-hour admin reports sent successfully")
            
        except Exception as e:
            logger.error(f"Error sending 2-hour admin reports: {e}", exc_info=True)


# Глобальный экземпляр
report_generator = ReportGenerator()

