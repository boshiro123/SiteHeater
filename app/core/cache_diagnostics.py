"""
Автодиагностика остывания кэша
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import statistics

import httpx

from app.core.db import db_manager

logger = logging.getLogger(__name__)


class CacheDiagnostics:
    """Автодиагностика для определения времени остывания кэша"""
    
    def __init__(self):
        self.active_diagnostics: Dict[int, asyncio.Task] = {}  # domain_id -> Task
    
    async def measure_response_time(self, url: str, timeout: int = 30) -> Optional[float]:
        """Измерение времени ответа одного URL"""
        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=timeout,
                follow_redirects=True
            ) as client:
                start_time = datetime.utcnow()
                response = await client.get(url)
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                
                if response.status_code == 200:
                    return elapsed
                return None
        except Exception as e:
            logger.debug(f"Error measuring {url}: {e}")
            return None
    
    async def run_diagnostic_test(
        self,
        domain_id: int,
        domain_name: str,
        urls: List[str],
        test_intervals: List[int],
        sample_size: int = 10,
        bot=None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Запуск полного теста диагностики кэша
        
        Args:
            domain_id: ID домена
            domain_name: Имя домена
            urls: Список URL для тестирования
            test_intervals: Интервалы между тестами в минутах [0, 5, 10, 15, 20, 30]
            sample_size: Количество URL для выборки
            bot: Бот для уведомлений
            user_id: ID пользователя
        """
        try:
            logger.info(f"🔬 Starting cache diagnostics for {domain_name}")
            
            # Отправляем уведомление о начале
            if bot and user_id:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🔬 <b>Начинаю диагностику кэша</b>\n\n"
                        f"🌐 Домен: <b>{domain_name}</b>\n"
                        f"🧪 Тестов: <b>{len(test_intervals)}</b>\n"
                        f"📊 Выборка: <b>{sample_size}</b> URL\n\n"
                        f"⏱ Это займет ~{max(test_intervals)} минут"
                    ),
                    parse_mode="HTML"
                )
            
            # Выбираем случайную выборку URL
            import random
            sample_urls = random.sample(urls, min(sample_size, len(urls)))
            
            results = []
            
            for interval_minutes in test_intervals:
                # Ждем перед следующим тестом
                if interval_minutes > 0:
                    logger.info(f"⏰ Waiting {interval_minutes} minutes before next test...")
                    await asyncio.sleep(interval_minutes * 60)
                
                logger.info(f"🧪 Test at T+{interval_minutes}m: measuring {len(sample_urls)} URLs")
                
                # Измеряем время ответа для каждого URL
                test_start = datetime.utcnow()
                times = []
                
                for url in sample_urls:
                    response_time = await self.measure_response_time(url)
                    if response_time:
                        times.append(response_time)
                    # Небольшая задержка между запросами
                    await asyncio.sleep(0.5)
                
                if times:
                    avg_time = statistics.mean(times)
                    median_time = statistics.median(times)
                    
                    results.append({
                        "interval_minutes": interval_minutes,
                        "timestamp": test_start,
                        "avg_time": avg_time,
                        "median_time": median_time,
                        "sample_count": len(times),
                        "times": times
                    })
                    
                    logger.info(
                        f"📊 T+{interval_minutes}m: "
                        f"avg={avg_time:.3f}s, median={median_time:.3f}s"
                    )
            
            # Анализ результатов
            analysis = self._analyze_results(results)
            
            # Отправляем результаты пользователю
            if bot and user_id:
                await self._send_diagnostic_report(
                    bot, user_id, domain_name, results, analysis
                )
            
            logger.info(f"✅ Cache diagnostics completed for {domain_name}")
            return {
                "domain_name": domain_name,
                "results": results,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Error in cache diagnostics for {domain_name}: {e}", exc_info=True)
            if bot and user_id:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Ошибка диагностики для {domain_name}: {str(e)}",
                    parse_mode="HTML"
                )
            raise
        finally:
            # Убираем из активных
            if domain_id in self.active_diagnostics:
                del self.active_diagnostics[domain_id]
    
    def _analyze_results(self, results: List[Dict]) -> Dict[str, Any]:
        """Анализ результатов диагностики"""
        if not results or len(results) < 2:
            return {"error": "Недостаточно данных для анализа"}
        
        # Базовое время (первый тест, кэш горячий после прогрева)
        base_time = results[0]["avg_time"]
        
        # Ищем точку, где время увеличивается значительно
        cooldown_threshold = 1.3  # Увеличение на 30% считаем остыванием
        cooldown_point = None
        
        for result in results[1:]:
            ratio = result["avg_time"] / base_time
            if ratio >= cooldown_threshold:
                cooldown_point = result["interval_minutes"]
                break
        
        # Рекомендуемый интервал прогрева
        if cooldown_point:
            recommended_interval = max(5, cooldown_point - 5)  # За 5 минут до остывания
        else:
            # Если не нашли точку остывания, берем самый большой интервал
            recommended_interval = results[-1]["interval_minutes"]
        
        # Процент увеличения времени
        time_increases = []
        for i in range(1, len(results)):
            increase = ((results[i]["avg_time"] - base_time) / base_time) * 100
            time_increases.append({
                "interval": results[i]["interval_minutes"],
                "increase_percent": increase
            })
        
        return {
            "base_time": base_time,
            "cooldown_point": cooldown_point,
            "recommended_interval_minutes": recommended_interval,
            "time_increases": time_increases,
            "max_time": max(r["avg_time"] for r in results),
            "conclusion": self._generate_conclusion(
                base_time, cooldown_point, recommended_interval
            )
        }
    
    def _generate_conclusion(
        self,
        base_time: float,
        cooldown_point: Optional[int],
        recommended_interval: int
    ) -> str:
        """Генерация вывода по результатам"""
        if cooldown_point:
            return (
                f"Кэш начинает остывать через ~{cooldown_point} минут. "
                f"Рекомендуется прогревать каждые {recommended_interval} минут."
            )
        else:
            return (
                f"Кэш остается стабильным. "
                f"Можно прогревать каждые {recommended_interval}+ минут."
            )
    
    async def _send_diagnostic_report(
        self,
        bot,
        user_id: int,
        domain_name: str,
        results: List[Dict],
        analysis: Dict
    ):
        """Отправка отчета о диагностике"""
        
        # Формируем график времени
        timeline = []
        for r in results:
            interval = r["interval_minutes"]
            avg_time = r["avg_time"]
            bars = "█" * int(avg_time * 10)  # Визуализация
            timeline.append(f"T+{interval:2d}m: {avg_time:.3f}s {bars}")
        
        # Формируем сообщение
        message = (
            f"🔬 <b>Результаты диагностики кэша</b>\n\n"
            f"🌐 Домен: <b>{domain_name}</b>\n\n"
            f"📊 <b>Динамика времени ответа:</b>\n"
            f"<code>{'  '.join(timeline)}</code>\n\n"
        )
        
        if "error" not in analysis:
            message += (
                f"📈 <b>Анализ:</b>\n"
                f"• Базовое время: <b>{analysis['base_time']:.3f}s</b>\n"
            )
            
            if analysis['cooldown_point']:
                message += (
                    f"• 🔥 Кэш остывает через: <b>~{analysis['cooldown_point']} минут</b>\n"
                )
            else:
                message += f"• ✅ Кэш стабилен во всех тестах\n"
            
            message += (
                f"• ⏰ Рекомендуемый интервал: <b>{analysis['recommended_interval_minutes']} минут</b>\n\n"
                f"💡 <b>Вывод:</b>\n"
                f"{analysis['conclusion']}"
            )
        else:
            message += f"⚠️ {analysis['error']}"
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending diagnostic report: {e}")
    
    async def start_diagnostic(
        self,
        domain_id: int,
        domain_name: str,
        urls: List[str],
        user_id: int,
        bot,
        test_intervals: Optional[List[int]] = None
    ) -> bool:
        """
        Запуск диагностики в фоновом режиме
        
        Args:
            test_intervals: Интервалы в минутах, например [0, 5, 10, 15, 20, 30]
        """
        if domain_id in self.active_diagnostics:
            logger.warning(f"Diagnostic already running for domain {domain_id}")
            return False
        
        # Интервалы по умолчанию: сразу, через 5, 10, 15, 20, 30 минут
        if test_intervals is None:
            test_intervals = [0, 5, 10, 15, 20, 30]
        
        task = asyncio.create_task(
            self.run_diagnostic_test(
                domain_id=domain_id,
                domain_name=domain_name,
                urls=urls,
                test_intervals=test_intervals,
                sample_size=10,
                bot=bot,
                user_id=user_id
            )
        )
        
        self.active_diagnostics[domain_id] = task
        logger.info(f"🚀 Started cache diagnostic for {domain_name}")
        return True
    
    def is_diagnostic_running(self, domain_id: int) -> bool:
        """Проверка, идет ли диагностика"""
        if domain_id in self.active_diagnostics:
            task = self.active_diagnostics[domain_id]
            return not task.done()
        return False


# Глобальный экземпляр
cache_diagnostics = CacheDiagnostics()

