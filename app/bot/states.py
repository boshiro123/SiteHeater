"""
Состояния FSM для бота
"""
from aiogram.fsm.state import State, StatesGroup


class AddDomainStates(StatesGroup):
    """Состояния для добавления домена"""
    waiting_for_domain = State()
    waiting_for_confirmation = State()
    waiting_for_custom_urls = State()

