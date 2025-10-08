"""
Обработчики диагностики кэша
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from app.core.db import db_manager
from app.core.cache_diagnostics import cache_diagnostics

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("diagnose_"))
async def callback_diagnose_cache(callback: CallbackQuery):
    """Запуск диагностики остывания кэша"""
    await callback.answer()
    
    domain_id = int(callback.data.split("_")[1])
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.message.answer("❌ Домен не найден или нет URL.")
        return
    
    # Проверяем, не идет ли уже диагностика
    if cache_diagnostics.is_diagnostic_running(domain_id):
        await callback.answer(
            "⚠️ Диагностика уже запущена для этого домена!",
            show_alert=True
        )
        return
    
    # Запускаем диагностику
    urls = [url.url for url in domain.urls]
    started = await cache_diagnostics.start_diagnostic(
        domain_id=domain_id,
        domain_name=domain.name,
        urls=urls,
        user_id=callback.from_user.id,
        bot=callback.bot
    )
    
    if started:
        await callback.message.answer(
            f"🔬 <b>Диагностика кэша запущена!</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"🧪 Тестов: <b>6</b> (T+0, 5, 10, 15, 20, 30 минут)\n"
            f"📊 Выборка: <b>10</b> случайных URL\n\n"
            f"⏱ Это займет ~30 минут\n"
            f"Результаты придут автоматически",
            parse_mode="HTML"
        )
    else:
        await callback.answer(
            "⚠️ Не удалось запустить диагностику",
            show_alert=True
        )


@router.message(Command("performance"))
async def cmd_performance(message: Message):
    """Команда /performance - советы по увеличению скорости"""
    tips = """
🚀 <b>Советы по увеличению скорости прогрева</b>

<b>1. Увеличьте WARMER_CONCURRENCY</b>
Текущее: 5 одновременных запросов
Рекомендация для вашего сервера: <b>15-20</b>

<code>WARMER_CONCURRENCY=15</code>

<b>2. Уменьшите задержки</b>
<code>WARMER_MIN_DELAY=0.3
WARMER_MAX_DELAY=1.0</code>

<b>3. Оптимизируйте chunk size</b>
Для больших доменов (1000+ URL):
<code>WARMER_CHUNK_SIZE=300</code>

<b>4. Уменьшите повторы (если кэш стабилен)</b>
<code>WARMER_REPEAT_COUNT=1</code>

<b>📊 Ожидаемое ускорение:</b>
• Было: ~45 минут на 1600 URL
• Станет: ~10-12 минут (3-4x быстрее!)

<b>⚙️ Оптимальная конфигурация для вашего сервера:</b>
<code>WARMER_CONCURRENCY=20
WARMER_MIN_DELAY=0.3
WARMER_MAX_DELAY=1.0
WARMER_CHUNK_SIZE=400
WARMER_REPEAT_COUNT=2</code>

<b>Чтобы применить:</b>
1. Отредактируйте .env
2. Перезапустите: <code>docker-compose restart app</code>

💡 <b>Совет:</b> Используйте /diagnose для определения оптимального интервала прогрева!
    """
    
    await message.answer(tips, parse_mode="HTML")

