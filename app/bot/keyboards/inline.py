"""
Inline клавиатуры для бота
"""
from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.domain import Domain


def get_confirm_urls_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения списка URL"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_urls"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data="reject_urls"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести свой список", callback_data="custom_urls"),
    )
    
    return builder.as_markup()


def get_domains_keyboard(domains: List[Domain]) -> InlineKeyboardMarkup:
    """Клавиатура со списком доменов"""
    builder = InlineKeyboardBuilder()
    
    for domain in domains:
        status = "🟢" if domain.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {domain.name}",
                callback_data=f"domain_{domain.id}"
            )
        )
    
    return builder.as_markup()


def get_domain_actions_keyboard(domain_id: int, has_active_job: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура действий с доменом"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🔥 Разовый прогрев", callback_data=f"warm_once_{domain_id}")
    )
    
    if not has_active_job:
        builder.row(
            InlineKeyboardButton(text="⏰ Настроить расписание", callback_data=f"schedule_{domain_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="⏹ Остановить прогрев", callback_data=f"stop_schedule_{domain_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔬 Диагностика кэша", callback_data=f"diagnose_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"stats_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="📋 Показать URL", callback_data=f"show_urls_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить домен", callback_data=f"delete_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="« Назад к списку", callback_data="back_to_domains")
    )
    
    return builder.as_markup()


def get_schedule_keyboard(domain_id: int, group: int = 3) -> InlineKeyboardMarkup:
    """Клавиатура выбора частоты прогрева"""
    builder = InlineKeyboardBuilder()
    
    schedules = [
        ("Каждые 5 минут", "5m"),
        ("Каждые 15 минут", "15m"),
        ("Каждые 30 минут", "30m"),
        ("Каждый час", "1h"),
        ("Каждые 2 часа", "2h"),
        ("Каждые 6 часов", "6h"),
    ]
    
    for text, schedule in schedules:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"set_schedule_{domain_id}_{group}_{schedule}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"domain_{domain_id}")
    )
    
    return builder.as_markup()


def get_delete_confirm_keyboard(domain_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения удаления"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{domain_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"domain_{domain_id}"),
    )
    
    return builder.as_markup()


def get_stats_period_keyboard(domain_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода статистики"""
    builder = InlineKeyboardBuilder()
    
    periods = [
        ("📅 Последние 24 часа", "24h"),
        ("📅 Последние 7 дней", "7d"),
        ("📅 Последние 30 дней", "30d"),
        ("📅 Вся история", "all"),
    ]
    
    for text, period in periods:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"show_stats_{domain_id}_{period}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"domain_{domain_id}")
    )
    
    return builder.as_markup()


def get_url_group_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора группы URL при добавлении домена"""
    builder = InlineKeyboardBuilder()
    
    groups = [
        ("🏠 Группа 1: Только главная", "group_1"),
        ("📄 Группа 2: Основные страницы", "group_2"),
        ("🌐 Группа 3: Все страницы", "group_3"),
    ]
    
    for text, callback in groups:
        builder.row(
            InlineKeyboardButton(text=text, callback_data=callback)
        )
    
    return builder.as_markup()


def get_diagnostic_mode_keyboard(domain_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора режима диагностики"""
    builder = InlineKeyboardBuilder()
    
    modes = [
        ("☀️ Только дневной тест (~15 мин)", "day"),
        ("🌙 Только ночной тест (~15 мин)", "night"),
        ("☀️🌙 Оба теста (~30 мин)", "both"),
    ]
    
    for text, mode in modes:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"diagnose_mode_{domain_id}_{mode}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"domain_{domain_id}")
    )
    
    return builder.as_markup()


def get_warming_group_keyboard(domain_id: int, action: str = "warm") -> InlineKeyboardMarkup:
    """
    Клавиатура выбора группы URL для прогрева
    
    Args:
        domain_id: ID домена
        action: "warm" для разового прогрева, "schedule" для настройки расписания
    """
    builder = InlineKeyboardBuilder()
    
    groups = [
        ("🏠 Группа 1: Только главная", "1"),
        ("📄 Группа 2: Основные страницы", "2"),
        ("🌐 Группа 3: Все страницы", "3"),
    ]
    
    for text, group in groups:
        builder.row(
            InlineKeyboardButton(
                text=text,
                callback_data=f"{action}_group_{domain_id}_{group}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"domain_{domain_id}")
    )
    
    return builder.as_markup()


def get_clients_keyboard(clients: List) -> InlineKeyboardMarkup:
    """Клавиатура со списком клиентов"""
    builder = InlineKeyboardBuilder()
    
    for client in clients:
        display_name = f"@{client.username}" if client.username else client.phone or f"ID:{client.id}"
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {display_name}",
                callback_data=f"client_{client.id}"
            )
        )
    
    return builder.as_markup()


def get_client_actions_keyboard(client_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с клиентом"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Домены клиента", callback_data=f"client_domains_{client_id}")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Привязать домен", callback_data=f"assign_domain_{client_id}")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад к списку", callback_data="back_to_clients")
    )
    
    return builder.as_markup()


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Простая клавиатура "Назад" """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back")
    )
    return builder.as_markup()


def get_select_client_keyboard(clients: List) -> InlineKeyboardMarkup:
    """Клавиатура выбора клиента для домена"""
    builder = InlineKeyboardBuilder()
    
    # Добавляем опцию "Без клиента" (для админов)
    builder.row(
        InlineKeyboardButton(text="🔹 Без клиента (админский домен)", callback_data="select_client_none")
    )
    
    # Добавляем клиентов
    for client in clients:
        display_name = f"@{client.username}" if client.username else client.phone or f"ID:{client.id}"
        builder.row(
            InlineKeyboardButton(
                text=f"👤 {display_name}",
                callback_data=f"select_client_{client.id}"
            )
        )
    
    return builder.as_markup()
