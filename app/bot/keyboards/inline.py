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
        InlineKeyboardButton(text="📋 Показать URL", callback_data=f"show_urls_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить домен", callback_data=f"delete_{domain_id}")
    )
    
    builder.row(
        InlineKeyboardButton(text="« Назад к списку", callback_data="back_to_domains")
    )
    
    return builder.as_markup()


def get_schedule_keyboard(domain_id: int) -> InlineKeyboardMarkup:
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
                callback_data=f"set_schedule_{domain_id}_{schedule}"
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

