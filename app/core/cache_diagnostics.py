"""
Продвинутая диагностика остывания кэша с методом "лестницы"
"""
import asyncio
import logging
import random
import statistics
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import httpx

from app.core.db import db_manager

logger = logging.getLogger(__name__)


class CacheDiagnostics:
    """
    Продвинутая диагностика кэша методом "лестницы"
    
    Метод:
    1. Берем 15 страниц (по приоритету из выбранной группы)
    2. Быстрый прогрев каждой страницы для получения базового времени
    3. "Лестница" 15 минут: каждую минуту проверяется одна страница
    4. Критерий остывания: время увеличилось в 2-3 раза
    5. Два окна: день и ночь
    6. Вывод: медианное время остывания и рекомендуемый интервал для дня/ночи
    """
    
    def __init__(self):
        self.active_diagnostics: Dict[int, asyncio.Task] = {}  # domain_id -> Task
    
    async def measure_response_time(
        self,
        url: str,
        repeat: int = 1,
        timeout: int = 30
    ) -> Optional[float]:
        """
        Измерение времени ответа URL
        
        Args:
            url: URL для проверки
            repeat: Количество повторов для усреднения
            timeout: Таймаут запроса
        
        Returns:
            Среднее время ответа в секундах или None при ошибке
        """
        times = []
        
        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=timeout,
                follow_redirects=True
            ) as client:
                for _ in range(repeat):
                    start_time = datetime.utcnow()
                    response = await client.get(url)
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    
                    if response.status_code == 200:
                        times.append(elapsed)
                    
                    # Небольшая задержка между повторами
                    if repeat > 1:
                        await asyncio.sleep(0.3)
            
            if times:
                return statistics.mean(times)
            return None
            
        except Exception as e:
            logger.debug(f"Error measuring {url}: {e}")
            return None
    
    async def fast_warmup(
        self,
        pages: List[str],
        bot=None,
        user_id: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Быстрый прогрев всех страниц для получения базового времени
        
        Args:
            pages: Список страниц для прогрева
            bot: Бот для уведомлений
            user_id: ID пользователя
        
        Returns:
            Словарь {url: base_time}
        """
        logger.info(f"🔥 Fast warmup of {len(pages)} pages...")
        
        if bot and user_id:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🔥 <b>Быстрый прогрев</b>\n\n"
                    f"Прогреваю {len(pages)} страниц для получения базового времени..."
                ),
                parse_mode="HTML"
            )
        
        base_times = {}
        
        for i, url in enumerate(pages, 1):
            # Делаем несколько запросов для надежного прогрева
            time = await self.measure_response_time(url, repeat=3)
            if time:
                base_times[url] = time
                logger.info(f"  [{i}/{len(pages)}] {url}: {time:.3f}s")
            else:
                logger.warning(f"  [{i}/{len(pages)}] {url}: failed")
            
            # Небольшая задержка
            await asyncio.sleep(0.5)
        
        logger.info(f"✅ Fast warmup completed: {len(base_times)}/{len(pages)} pages warmed")
        return base_times
    
    async def ladder_test(
        self,
        pages: List[str],
        base_times: Dict[str, float],
        time_window: str = "day",
        bot=None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Тест методом "лестницы" - 15 минут, каждую минуту одна страница
        
        Args:
            pages: Список из 15 страниц
            base_times: Базовые времена {url: time}
            time_window: "day" или "night"
            bot: Бот для уведомлений
            user_id: ID пользователя
        
        Returns:
            Результаты теста
        """
        window_emoji = "☀️" if time_window == "day" else "🌙"
        logger.info(f"{window_emoji} Starting ladder test ({time_window})...")
        
        if bot and user_id:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"{window_emoji} <b>Тест лестницей ({time_window})</b>\n\n"
                    f"Каждую минуту проверяется 1 страница...\n"
                    f"⏱ Это займет ~15 минут"
                ),
                parse_mode="HTML"
            )
        
        results = {}
        cooldown_threshold = 2.0  # Остывание = время увеличилось в 2+ раза
        
        for minute, url in enumerate(pages, 1):
            # Ждем до следующей минуты (первая - сразу)
            if minute > 1:
                logger.info(f"⏰ Waiting for minute {minute}...")
                await asyncio.sleep(60)  # 1 минута
            
            # Проверяем страницу
            current_time = await self.measure_response_time(url, repeat=1)
            
            if url not in base_times or not current_time:
                logger.warning(f"  [Minute {minute}] {url}: no data")
                continue
            
            base_time = base_times[url]
            ratio = current_time / base_time
            
            # Определяем статус
            if ratio >= cooldown_threshold:
                status = "❄️ ОСТЫЛО"
                cooldown_minute = minute
            elif ratio >= 1.5:
                status = "🟡 Теплеет"
                cooldown_minute = None
            else:
                status = "🔥 Горячо"
                cooldown_minute = None
            
            results[url] = {
                "minute": minute,
                "base_time": base_time,
                "current_time": current_time,
                "ratio": ratio,
                "status": status,
                "cooldown_minute": cooldown_minute
            }
            
            logger.info(
                f"  [Minute {minute:2d}] {url[:50]}... "
                f"base={base_time:.3f}s current={current_time:.3f}s "
                f"ratio={ratio:.2f}x {status}"
            )
        
        logger.info(f"✅ Ladder test ({time_window}) completed")
        return results
    
    def analyze_results(
        self,
        day_results: Dict[str, Any],
        night_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Анализ результатов тестов
        
        Args:
            day_results: Результаты дневного теста
            night_results: Результаты ночного теста (опционально)
        
        Returns:
            Анализ с рекомендациями
        """
        def analyze_window(results: Dict[str, Any], window_name: str) -> Dict:
            cooldown_minutes = [
                r["cooldown_minute"] 
                for r in results.values() 
                if r.get("cooldown_minute")
            ]
            
            if cooldown_minutes:
                median_cooldown = statistics.median(cooldown_minutes)
                # Рекомендуем прогрев чуть чаще медианы
                recommended_interval = max(5, int(median_cooldown) - 2)
            else:
                # Если ничего не остыло за 15 минут
                median_cooldown = 15
                recommended_interval = 12
            
            return {
                "window": window_name,
                "cooldown_pages": len(cooldown_minutes),
                "total_pages": len(results),
                "median_cooldown_minute": median_cooldown,
                "recommended_interval": recommended_interval,
                "cooldown_minutes": cooldown_minutes
            }
        
        analysis = {
            "day": analyze_window(day_results, "день")
        }
        
        if night_results:
            analysis["night"] = analyze_window(night_results, "ночь")
        
        return analysis
    
    async def run_diagnostic_test(
        self,
        domain_id: int,
        domain_name: str,
        urls: List[str],
        test_mode: str = "day",  # "day", "night", или "both"
        bot=None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Запуск полного теста диагностики
        
        Args:
            domain_id: ID домена
            domain_name: Имя домена
            urls: Список URL для тестирования
            test_mode: "day" (только день), "night" (только ночь), "both" (оба)
            bot: Бот для уведомлений
            user_id: ID пользователя
        """
        try:
            logger.info(f"🔬 Starting advanced cache diagnostics for {domain_name} (mode: {test_mode})")
            
            # Отправляем уведомление о начале
            if bot and user_id:
                mode_text = {
                    "day": "☀️ дневной тест",
                    "night": "🌙 ночной тест",
                    "both": "☀️ дневной + 🌙 ночной тесты"
                }
                
                duration = 15 if test_mode in ["day", "night"] else 30
                
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🔬 <b>Начинаю продвинутую диагностику</b>\n\n"
                        f"🌐 Домен: <b>{domain_name}</b>\n"
                        f"📊 Режим: {mode_text[test_mode]}\n"
                        f"📄 Страниц: <b>15</b>\n"
                        f"⏱ Длительность: <b>~{duration} минут</b>\n\n"
                        f"Метод: Лестница (каждая страница проверяется каждую минуту)"
                    ),
                    parse_mode="HTML"
                )
            
            # Выбираем 15 страниц (случайная выборка)
            sample_size = min(15, len(urls))
            pages = random.sample(urls, sample_size)
            
            logger.info(f"Selected {len(pages)} pages for testing")
            
            # Шаг 1: Быстрый прогрев
            base_times = await self.fast_warmup(pages, bot, user_id)
            
            if len(base_times) < 5:
                raise Exception(f"Too few pages warmed successfully: {len(base_times)}/15")
            
            # Фильтруем только успешно прогретые страницы
            pages = [p for p in pages if p in base_times]
            
            # Шаг 2: Тесты лестницей
            day_results = None
            night_results = None
            
            if test_mode in ["day", "both"]:
                day_results = await self.ladder_test(pages, base_times, "day", bot, user_id)
            
            if test_mode in ["night", "both"]:
                if test_mode == "both":
                    # Между тестами делаем небольшую паузу
                    if bot and user_id:
                        await bot.send_message(
                            chat_id=user_id,
                            text="✅ Дневной тест завершен!\n\n⏸ Пауза 2 минуты перед ночным тестом...",
                            parse_mode="HTML"
                        )
                    await asyncio.sleep(120)  # 2 минуты паузы
                
                night_results = await self.ladder_test(pages, base_times, "night", bot, user_id)
            
            # Шаг 3: Анализ
            analysis = self.analyze_results(day_results, night_results)
            
            # Шаг 4: Отправляем результаты
            if bot and user_id:
                await self._send_diagnostic_report(
                    bot, user_id, domain_name, pages, base_times,
                    day_results, night_results, analysis
                )
            
            logger.info(f"✅ Cache diagnostics completed for {domain_name}")
            
            return {
                "domain_name": domain_name,
                "pages": pages,
                "base_times": base_times,
                "day_results": day_results,
                "night_results": night_results,
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
    
    async def _send_diagnostic_report(
        self,
        bot,
        user_id: int,
        domain_name: str,
        pages: List[str],
        base_times: Dict[str, float],
        day_results: Optional[Dict[str, Any]],
        night_results: Optional[Dict[str, Any]],
        analysis: Dict[str, Any]
    ):
        """Отправка отчета о диагностике"""
        
        def format_results_table(results: Dict[str, Any]) -> str:
            """Форматирование таблицы результатов"""
            lines = []
            for url, data in results.items():
                minute = data["minute"]
                status_icon = "🔥" if data["ratio"] < 1.5 else "🟡" if data["ratio"] < 2.0 else "❄️"
                short_url = url.split('/')[-1][:20] if '/' in url else url[:20]
                lines.append(f"M{minute:2d}│ {status_icon} {data['current_time']:.2f}s │ {short_url}...")
            return "\n".join(lines)
        
        # Формируем сообщение
        message = (
            f"🔬 <b>Результаты диагностики кэша</b>\n\n"
            f"🌐 Домен: <b>{domain_name}</b>\n"
            f"📄 Протестировано: <b>{len(pages)}</b> страниц\n\n"
        )
        
        # Дневной тест
        if day_results:
            day_analysis = analysis["day"]
            message += (
                f"☀️ <b>Дневной тест:</b>\n"
                f"• Остыло страниц: <b>{day_analysis['cooldown_pages']}/{day_analysis['total_pages']}</b>\n"
                f"• Медианное остывание: <b>~{day_analysis['median_cooldown_minute']:.0f} минут</b>\n"
                f"• ⏰ Рекомендуемый интервал: <b>{day_analysis['recommended_interval']} минут</b>\n\n"
            )
        
        # Ночной тест
        if night_results:
            night_analysis = analysis["night"]
            message += (
                f"🌙 <b>Ночной тест:</b>\n"
                f"• Остыло страниц: <b>{night_analysis['cooldown_pages']}/{night_analysis['total_pages']}</b>\n"
                f"• Медианное остывание: <b>~{night_analysis['median_cooldown_minute']:.0f} минут</b>\n"
                f"• ⏰ Рекомендуемый интервал: <b>{night_analysis['recommended_interval']} минут</b>\n\n"
            )
        
        # Вывод
        message += "💡 <b>Рекомендации:</b>\n"
        
        if day_results and night_results:
            day_int = analysis["day"]["recommended_interval"]
            night_int = analysis["night"]["recommended_interval"]
            message += (
                f"Настройте два расписания:\n"
                f"• ☀️ День (10:00-22:00): каждые <b>{day_int} минут</b>\n"
                f"• 🌙 Ночь (22:00-10:00): каждые <b>{night_int} минут</b>\n\n"
                f"Это оптимизирует нагрузку и сэкономит ресурсы!"
            )
        elif day_results:
            interval = analysis["day"]["recommended_interval"]
            message += f"Прогревайте каждые <b>{interval} минут</b>"
        elif night_results:
            interval = analysis["night"]["recommended_interval"]
            message += f"Прогревайте каждые <b>{interval} минут</b>"
        
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
        test_mode: str = "day"
    ) -> bool:
        """
        Запуск диагностики в фоновом режиме
        
        Args:
            domain_id: ID домена
            domain_name: Имя домена
            urls: Список URL
            user_id: ID пользователя
            bot: Бот
            test_mode: "day", "night", или "both"
        
        Returns:
            True если запущено успешно
        """
        if domain_id in self.active_diagnostics:
            logger.warning(f"Diagnostic already running for domain {domain_id}")
            return False
        
        if len(urls) < 5:
            logger.warning(f"Too few URLs for diagnostics: {len(urls)}")
            return False
        
        task = asyncio.create_task(
            self.run_diagnostic_test(
                domain_id=domain_id,
                domain_name=domain_name,
                urls=urls,
                test_mode=test_mode,
                bot=bot,
                user_id=user_id
            )
        )
        
        self.active_diagnostics[domain_id] = task
        logger.info(f"🚀 Started cache diagnostic for {domain_name} (mode: {test_mode})")
        return True
    
    def is_diagnostic_running(self, domain_id: int) -> bool:
        """Проверка, идет ли диагностика"""
        if domain_id in self.active_diagnostics:
            task = self.active_diagnostics[domain_id]
            return not task.done()
        return False


# Глобальный экземпляр
cache_diagnostics = CacheDiagnostics()
