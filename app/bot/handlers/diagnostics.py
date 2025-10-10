"""
Обработчики диагностики кэша
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command

from app.core.db import db_manager
from app.core.cache_diagnostics import cache_diagnostics
from app.bot.keyboards.inline import get_diagnostic_mode_keyboard
from app.utils.url_grouper import url_grouper

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data.startswith("diagnose_"))
async def callback_diagnose_cache(callback: CallbackQuery):
    """Показать выбор режима диагностики"""
    await callback.answer()
    
    # Проверяем, это не режим диагностики
    if callback.data.startswith("diagnose_mode_"):
        return await callback_diagnose_mode(callback)
    
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
    
    # Получаем статистику по группам
    urls = [url.url for url in domain.urls]
    group = domain.url_group
    
    # Фильтруем URL по выбранной группе
    filtered_urls = url_grouper.filter_urls_by_group(urls, domain.name, group)
    
    group_desc = url_grouper.get_group_description(group)
    
    await callback.message.edit_text(
        f"🔬 <b>Диагностика кэша</b>\n\n"
        f"🌐 Домен: <b>{domain.name}</b>\n"
        f"📊 Группа: {group_desc}\n"
        f"📄 Страниц: <b>{len(filtered_urls)}</b>\n\n"
        f"Выберите режим диагностики:",
        parse_mode="HTML",
        reply_markup=get_diagnostic_mode_keyboard(domain_id)
    )


@router.callback_query(F.data.startswith("diagnose_mode_"))
async def callback_diagnose_mode(callback: CallbackQuery):
    """Запуск диагностики с выбранным режимом"""
    await callback.answer("🔬 Запускаю диагностику...")
    
    parts = callback.data.split("_")
    domain_id = int(parts[2])
    test_mode = parts[3]  # day, night или both
    
    domain = await db_manager.get_domain_by_id(domain_id)
    
    if not domain or not domain.urls:
        await callback.message.edit_text("❌ Домен не найден или нет URL.")
        return
    
    # Получаем URL по группе
    all_urls = [url.url for url in domain.urls]
    urls = url_grouper.filter_urls_by_group(all_urls, domain.name, domain.url_group)
    
    if len(urls) < 5:
        await callback.message.edit_text(
            f"❌ Недостаточно URL для диагностики ({len(urls)}).\n"
            f"Минимум: 5 страниц"
        )
        return
    
    # Запускаем диагностику
    started = await cache_diagnostics.start_diagnostic(
        domain_id=domain_id,
        domain_name=domain.name,
        urls=urls,
        user_id=callback.from_user.id,
        bot=callback.bot,
        test_mode=test_mode
    )
    
    if started:
        mode_text = {
            "day": "☀️ дневной тест (~15 мин)",
            "night": "🌙 ночной тест (~15 мин)",
            "both": "☀️🌙 оба теста (~30 мин)"
        }
        
        await callback.message.edit_text(
            f"🔬 <b>Диагностика запущена!</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"📊 Режим: {mode_text[test_mode]}\n"
            f"📄 Страниц: <b>15</b> (случайная выборка)\n\n"
            f"Метод: <b>Лестница</b> (каждую минуту одна страница)\n\n"
            f"Результаты придут автоматически ⏱",
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

