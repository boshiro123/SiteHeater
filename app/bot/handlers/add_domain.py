"""
Обработчики добавления домена
"""
import logging
from urllib.parse import urlparse

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.bot.states import AddDomainStates
from app.bot.keyboards.inline import get_confirm_urls_keyboard
from app.core.db import db_manager
from app.utils.sitemap import sitemap_parser

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("add"))
async def cmd_add_domain(message: Message, state: FSMContext):
    """Команда /add <domain>"""
    # Парсим домен из команды
    text = message.text.strip()
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите домен.\n\n"
            "Использование: <code>/add example.com</code>",
            parse_mode="HTML"
        )
        return
    
    domain = parts[1].strip()
    
    # Нормализуем домен
    if domain.startswith(('http://', 'https://')):
        parsed = urlparse(domain)
        domain = parsed.netloc
    
    if not domain:
        await message.answer("❌ Неверный формат домена.")
        return
    
    # Проверяем, существует ли уже такой домен
    existing_domain = await db_manager.get_domain_by_name(domain)
    if existing_domain and existing_domain.user_id == message.from_user.id:
        await message.answer(
            f"⚠️ Домен <b>{domain}</b> уже добавлен.\n"
            f"Используйте /domains для управления.",
            parse_mode="HTML"
        )
        return
    
    # Отправляем сообщение о начале поиска
    status_msg = await message.answer(
        f"🔍 Ищу страницы для домена <b>{domain}</b>...\n"
        f"Это может занять некоторое время.",
        parse_mode="HTML"
    )
    
    try:
        # Пытаемся найти URL
        urls = await sitemap_parser.discover_urls(domain)
        
        if not urls:
            await status_msg.edit_text(
                f"❌ Не удалось найти страницы для <b>{domain}</b>.\n\n"
                f"Вы можете ввести список URL вручную:\n"
                f"Отправьте URL через запятую или каждый с новой строки.",
                parse_mode="HTML"
            )
            await state.set_state(AddDomainStates.waiting_for_custom_urls)
            await state.update_data(domain=domain)
            return
        
        # Ограничиваем количество URL для отображения
        display_urls = urls[:10]
        urls_text = "\n".join(f"• {url}" for url in display_urls)
        
        if len(urls) > 10:
            urls_text += f"\n\n... и еще {len(urls) - 10} URL"
        
        await status_msg.edit_text(
            f"✅ Найдено <b>{len(urls)}</b> страниц для <b>{domain}</b>:\n\n"
            f"{urls_text}\n\n"
            f"Что делать с этим списком?",
            parse_mode="HTML",
            reply_markup=get_confirm_urls_keyboard()
        )
        
        # Сохраняем данные в состояние
        await state.set_state(AddDomainStates.waiting_for_confirmation)
        await state.update_data(domain=domain, urls=urls, message_id=status_msg.message_id)
        
    except Exception as e:
        logger.error(f"Error discovering URLs for {domain}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ Произошла ошибка при поиске страниц.\n\n"
            f"Вы можете ввести список URL вручную:\n"
            f"Отправьте URL через запятую или каждый с новой строки.",
            parse_mode="HTML"
        )
        await state.set_state(AddDomainStates.waiting_for_custom_urls)
        await state.update_data(domain=domain)


@router.callback_query(F.data == "confirm_urls", AddDomainStates.waiting_for_confirmation)
async def callback_confirm_urls(callback: CallbackQuery, state: FSMContext):
    """Подтверждение списка URL"""
    await callback.answer()
    
    data = await state.get_data()
    domain = data.get("domain")
    urls = data.get("urls", [])
    
    if not domain or not urls:
        await callback.message.edit_text("❌ Ошибка: данные не найдены.")
        await state.clear()
        return
    
    try:
        # Сохраняем в базу
        await db_manager.create_domain(
            name=domain,
            user_id=callback.from_user.id,
            urls=urls
        )
        
        await callback.message.edit_text(
            f"✅ Домен <b>{domain}</b> успешно добавлен!\n\n"
            f"Сохранено <b>{len(urls)}</b> страниц.\n\n"
            f"Используйте /domains для управления.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error saving domain {domain}: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при сохранении домена: {str(e)}"
        )
    
    await state.clear()


@router.callback_query(F.data == "reject_urls", AddDomainStates.waiting_for_confirmation)
async def callback_reject_urls(callback: CallbackQuery, state: FSMContext):
    """Отклонение списка URL"""
    await callback.answer()
    
    await callback.message.edit_text(
        "❌ Отменено. Используйте /add для повторной попытки."
    )
    
    await state.clear()


@router.callback_query(F.data == "custom_urls", AddDomainStates.waiting_for_confirmation)
async def callback_custom_urls(callback: CallbackQuery, state: FSMContext):
    """Переход к вводу пользовательского списка URL"""
    await callback.answer()
    
    await callback.message.edit_text(
        "✏️ Отправьте список URL.\n\n"
        "Формат: через запятую или каждый URL с новой строки.\n\n"
        "Пример:\n"
        "<code>https://example.com/page1, https://example.com/page2</code>\n\n"
        "или\n\n"
        "<code>https://example.com/page1\n"
        "https://example.com/page2</code>",
        parse_mode="HTML"
    )
    
    await state.set_state(AddDomainStates.waiting_for_custom_urls)


@router.message(AddDomainStates.waiting_for_custom_urls)
async def process_custom_urls(message: Message, state: FSMContext):
    """Обработка пользовательского списка URL"""
    text = message.text.strip()
    
    # Парсим URL
    urls = []
    
    # Пробуем разделить по запятой
    if ',' in text:
        urls = [url.strip() for url in text.split(',')]
    else:
        # Пробуем разделить по переносам строк
        urls = [url.strip() for url in text.split('\n')]
    
    # Фильтруем пустые строки и невалидные URL
    valid_urls = []
    for url in urls:
        if url and url.startswith(('http://', 'https://')):
            valid_urls.append(url)
    
    if not valid_urls:
        await message.answer(
            "❌ Не найдено валидных URL.\n\n"
            "URL должны начинаться с http:// или https://",
        )
        return
    
    data = await state.get_data()
    domain = data.get("domain")
    
    if not domain:
        await message.answer("❌ Ошибка: домен не найден. Используйте /add заново.")
        await state.clear()
        return
    
    try:
        # Сохраняем в базу
        await db_manager.create_domain(
            name=domain,
            user_id=message.from_user.id,
            urls=valid_urls
        )
        
        await message.answer(
            f"✅ Домен <b>{domain}</b> успешно добавлен!\n\n"
            f"Сохранено <b>{len(valid_urls)}</b> страниц.\n\n"
            f"Используйте /domains для управления.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error saving domain {domain}: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при сохранении домена: {str(e)}"
        )
    
    await state.clear()

