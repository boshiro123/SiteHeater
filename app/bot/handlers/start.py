"""
Обработчик команды /start
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    welcome_text = """
🔥 <b>Добро пожаловать в SiteHeater!</b>

Этот бот поможет вам "прогревать" кэш ваших сайтов, автоматически посещая их страницы.

<b>Доступные команды:</b>
/add <i>&lt;domain&gt;</i> - Добавить новый домен
/domains - Список всех доменов
/status - Активные прогревы
/help - Справка

<b>Как это работает?</b>
1️⃣ Добавьте домен через /add
2️⃣ Бот найдет все страницы (sitemap + краулинг)
3️⃣ Настройте расписание или запустите разовый прогрев
4️⃣ Бот будет автоматически посещать ваши страницы

<b>🚀 Параллельный прогрев:</b>
Можно прогревать несколько сайтов одновременно!

Начните с команды /add example.com
    """
    
    await message.answer(welcome_text, parse_mode="HTML")

