"""
Обработчик команды /start
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.core.db import db_manager

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Проверяем, есть ли приглашение для этого пользователя
    pending = await db_manager.get_pending_client_by_username_or_phone(
        username=message.from_user.username,
        phone=None  # Telegram не передает phone через API
    )
    
    # Получаем пользователя (middleware уже создал/обновил его)
    user = await db_manager.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Если было приглашение - активируем клиента и удаляем приглашение
    if pending:
        # Устанавливаем роль клиента
        user = await db_manager.set_user_role(user.id, "client")
        
        # Удаляем приглашение
        await db_manager.delete_pending_client(pending.id)
        
        # Отправляем особое приветствие
        await message.answer(
            "✅ <b>Добро пожаловать!</b>\n\n"
            "Ваш аккаунт успешно активирован!\n\n"
            "Администратор может теперь привязать к вам домены.\n"
            "После привязки доменов вы сможете:\n"
            "• Просматривать их через /domains\n"
            "• Получать ежедневные отчеты в 9:00\n\n"
            "<b>Доступные команды:</b>\n"
            "/domains - Ваши домены\n"
            "/status - Активные прогревы\n"
            "/help - Справка",
            parse_mode="HTML"
        )
        
        logger.info(f"Activated client {user.id} from pending invitation")
        return
    
    if user.role == "admin":
        welcome_text = """
🔥 <b>Добро пожаловать, Администратор!</b>

Этот бот поможет вам "прогревать" кэш сайтов ваших клиентов, автоматически посещая их страницы.

<b>Административные команды:</b>
/clients - Управление клиентами
/add_client - Добавить нового клиента
/add <i>&lt;domain&gt;</i> - Добавить домен
/domains - Список всех доменов
/status - Активные прогревы
/help - Справка

<b>Как это работает?</b>
1️⃣ Добавьте клиента через /add_client
2️⃣ Добавьте домен и привяжите к клиенту
3️⃣ Настройте расписание или запустите разовый прогрев
4️⃣ Бот будет автоматически посещать страницы

<b>📊 Отчеты:</b>
Ежедневные отчеты приходят автоматически в 9:00
        """
    elif user.role == "client":
        # Проверяем, есть ли у клиента домены
        domains = await db_manager.get_domains_by_client(user.id)
        
        if domains:
            welcome_text = f"""
✅ <b>Добро пожаловать!</b>

У вас <b>{len(domains)}</b> {'сайт' if len(domains) == 1 else 'сайта' if len(domains) < 5 else 'сайтов'} в мониторинге.

<b>Доступные команды:</b>
/domains - Просмотр ваших сайтов
/help - Справка

<b>📊 Ежедневные отчеты:</b>
Каждое утро в 9:00 вы получаете подробный отчет о работе ваших сайтов за последние 24 часа.

💡 <i>Наша система автоматически следит за быстродействием ваших сайтов</i>

По всем вопросам обращайтесь к администратору.
            """
        else:
            welcome_text = """
✅ <b>Добро пожаловать!</b>

У вас пока нет подключенных сайтов.

Обратитесь к администратору для подключения ваших сайтов к системе мониторинга.

<b>Доступные команды:</b>
/help - Справка
            """
    else:
        # Неизвестная роль (не должно происходить)
        welcome_text = """
👋 <b>Добро пожаловать!</b>

Для получения доступа обратитесь к администратору.
        """
    
    await message.answer(welcome_text.strip(), parse_mode="HTML")


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

