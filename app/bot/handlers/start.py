"""
Обработчик команды /start
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.core.db import db_manager

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Получаем пользователя (middleware уже создал/обновил его)
    user = await db_manager.register_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
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
✅ <b>Добро пожаловать, вы верифицированы!</b>

У вас <b>{len(domains)}</b> доменов в прогреве.

<b>Доступные команды:</b>
/domains - Ваши домены
/status - Активные прогревы

<b>📊 Отчеты:</b>
Ежедневные отчеты приходят автоматически в 9:00

По всем вопросам обращайтесь к администратору.
            """
        else:
            welcome_text = """
✅ <b>Добро пожаловать, вы верифицированы!</b>

У вас пока нет доменов в прогреве.

Обратитесь к администратору для добавления доменов.

<b>📊 Отчеты:</b>
Ежедневные отчеты будут приходить автоматически в 9:00
            """
    else:
        # Неизвестная роль (не должно происходить)
        welcome_text = """
👋 <b>Добро пожаловать!</b>

Для получения доступа обратитесь к администратору.
        """
    
    await message.answer(welcome_text.strip(), parse_mode="HTML")

