"""
Обработчики команд для администраторов
"""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.core.db import db_manager
from app.bot.keyboards.inline import get_clients_keyboard, get_client_actions_keyboard, get_back_keyboard
from app.bot.middlewares.role_check import AdminOnlyMiddleware

logger = logging.getLogger(__name__)
router = Router()

# Применяем middleware только к этому роутеру
router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyMiddleware())


class AddClientStates(StatesGroup):
    """Состояния для добавления клиента"""
    waiting_for_identifier = State()


@router.message(Command("clients"))
async def cmd_clients(message: Message):
    """Список всех клиентов"""
    clients = await db_manager.get_all_clients()
    
    if not clients:
        await message.answer(
            "📋 <b>Список клиентов пуст</b>\n\n"
            "Используйте /add_client для добавления нового клиента.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f"👥 <b>Клиенты ({len(clients)})</b>\n\n"
        f"Выберите клиента для управления:",
        parse_mode="HTML",
        reply_markup=get_clients_keyboard(clients)
    )


@router.callback_query(F.data.startswith("client_") & ~F.data.startswith("client_domains_"))
async def callback_client_details(callback: CallbackQuery):
    """Детали клиента"""
    await callback.answer()
    
    client_id = int(callback.data.split("_")[1])
    
    # Получаем клиента
    user = await db_manager.register_user(client_id, None, None, None)
    
    if not user:
        await callback.message.edit_text("❌ Клиент не найден.")
        return
    
    # Получаем домены клиента
    domains = await db_manager.get_domains_by_client(client_id)
    
    domains_text = ""
    if domains:
        domains_text = "\n\n📋 <b>Домены:</b>\n"
        for domain in domains:
            domains_text += f"• {domain.name} ({len(domain.urls)} страниц)\n"
    else:
        domains_text = "\n\n📋 <b>Доменов пока нет</b>"
    
    await callback.message.edit_text(
        f"👤 <b>Клиент</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: @{user.username or 'не указан'}\n"
        f"📱 Телефон: {user.phone or 'не указан'}\n"
        f"📅 Регистрация: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{domains_text}",
        parse_mode="HTML",
        reply_markup=get_client_actions_keyboard(client_id)
    )


@router.callback_query(F.data.startswith("client_domains_"))
async def callback_client_domains(callback: CallbackQuery):
    """Показать домены клиента"""
    await callback.answer()
    
    client_id = int(callback.data.split("_")[2])
    
    # Получаем домены клиента
    domains = await db_manager.get_domains_by_client(client_id)
    
    if not domains:
        await callback.message.edit_text(
            "📋 <b>У клиента пока нет доменов</b>\n\n"
            "Используйте /add для добавления домена и привязки к клиенту.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    domains_text = "📋 <b>Домены клиента:</b>\n\n"
    for domain in domains:
        status = "🟢" if domain.is_active else "🔴"
        domains_text += f"{status} <b>{domain.name}</b>\n"
        domains_text += f"   📊 Страниц: {len(domain.urls)}\n"
        domains_text += f"   📅 Добавлен: {domain.created_at.strftime('%Y-%m-%d')}\n\n"
    
    await callback.message.edit_text(
        domains_text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )


@router.callback_query(F.data == "back")
async def callback_back(callback: CallbackQuery):
    """Универсальная кнопка назад"""
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data == "back_to_clients")
async def callback_back_to_clients(callback: CallbackQuery):
    """Вернуться к списку клиентов"""
    await callback.answer()
    
    clients = await db_manager.get_all_clients()
    
    await callback.message.edit_text(
        f"👥 <b>Клиенты ({len(clients)})</b>\n\n"
        f"Выберите клиента для управления:",
        parse_mode="HTML",
        reply_markup=get_clients_keyboard(clients)
    )


@router.message(Command("add_client"))
async def cmd_add_client(message: Message, state: FSMContext):
    """Начало процесса добавления клиента"""
    await message.answer(
        "➕ <b>Добавление клиента</b>\n\n"
        "Отправьте username (например @username) или телефон клиента.\n\n"
        "Клиент должен сначала запустить бота командой /start",
        parse_mode="HTML"
    )
    await state.set_state(AddClientStates.waiting_for_identifier)


@router.message(AddClientStates.waiting_for_identifier)
async def process_client_identifier(message: Message, state: FSMContext):
    """Обработка username или телефона клиента"""
    identifier = message.text.strip()
    
    # Ищем пользователя
    user = await db_manager.get_user_by_username_or_phone(identifier)
    
    if not user:
        await message.answer(
            "❌ Пользователь не найден.\n\n"
            "Убедитесь, что:\n"
            "1. Пользователь запустил бота командой /start\n"
            "2. Username или телефон указаны правильно\n\n"
            "Попробуйте еще раз или /cancel для отмены.",
            parse_mode="HTML"
        )
        return
    
    if user.role == "admin":
        await message.answer(
            "❌ Этот пользователь уже является администратором.\n\n"
            "Попробуйте другого или /cancel для отмены.",
            parse_mode="HTML"
        )
        return
    
    # Устанавливаем роль клиента (если еще не установлена)
    if user.role != "client":
        user = await db_manager.set_user_role(user.id, "client")
    
    await message.answer(
        f"✅ <b>Клиент добавлен!</b>\n\n"
        f"👤 Username: @{user.username or 'не указан'}\n"
        f"📱 Телефон: {user.phone or 'не указан'}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"Теперь вы можете привязать к нему домены через /add",
        parse_mode="HTML"
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("assign_domain_"))
async def callback_assign_domain(callback: CallbackQuery):
    """Привязка домена к клиенту - показываем список доменов"""
    await callback.answer()
    
    client_id = int(callback.data.split("_")[2])
    
    # Получаем все домены
    all_domains = await db_manager.get_domains()
    
    if not all_domains:
        await callback.message.edit_text(
            "📋 <b>Нет доступных доменов</b>\n\n"
            "Сначала добавьте домены через /add",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Получаем уже привязанные домены клиента
    client_domains = await db_manager.get_domains_by_client(client_id)
    client_domain_ids = [d.id for d in client_domains]
    
    # Фильтруем домены: показываем только те, что еще не привязаны к этому клиенту
    available_domains = [d for d in all_domains if d.id not in client_domain_ids]
    
    if not available_domains:
        await callback.message.edit_text(
            "📋 <b>Нет доступных доменов для привязки</b>\n\n"
            "Все домены уже привязаны к этому клиенту.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        return
    
    # Создаем клавиатуру с доступными доменами
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for domain in available_domains:
        builder.row(
            InlineKeyboardButton(
                text=f"🌐 {domain.name} ({len(domain.urls)} URL)",
                callback_data=f"link_domain_{client_id}_{domain.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"client_{client_id}")
    )
    
    await callback.message.edit_text(
        "🔗 <b>Выберите домен для привязки:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("link_domain_"))
async def callback_link_domain(callback: CallbackQuery):
    """Привязываем выбранный домен к клиенту"""
    await callback.answer()
    
    parts = callback.data.split("_")
    client_id = int(parts[2])
    domain_id = int(parts[3])
    
    try:
        # Привязываем домен к клиенту
        domain = await db_manager.assign_domain_to_client(domain_id, client_id)
        
        # Получаем информацию о клиенте
        user = await db_manager.register_user(client_id, None, None, None)
        
        await callback.message.edit_text(
            f"✅ <b>Домен привязан!</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"👤 Клиент: @{user.username or user.phone or f'ID:{user.id}'}\n\n"
            f"Теперь клиент может управлять этим доменом и будет получать отчеты.",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
        
        logger.info(f"Domain {domain.name} (ID:{domain_id}) assigned to client {client_id}")
        
    except Exception as e:
        logger.error(f"Error linking domain {domain_id} to client {client_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при привязке домена:\n{str(e)}",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )


# Экспортируем роутер
__all__ = ['router']

