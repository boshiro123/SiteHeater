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


class RestoreBackupStates(StatesGroup):
    """Состояния для восстановления бэкапа"""
    waiting_for_backup_selection = State()
    waiting_for_confirmation = State()


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
    user = await db_manager.get_user_by_id(client_id)
    
    if not user:
        await callback.message.edit_text("❌ Клиент не найден.")
        return
    
    # Получаем домены клиента
    domains = await db_manager.get_domains_by_client(client_id)
    
    # Формируем отображаемое имя
    display_name = ""
    if user.first_name:
        display_name = user.first_name
        if user.last_name:
            display_name += f" {user.last_name}"
    elif user.username:
        display_name = f"@{user.username}"
    else:
        display_name = f"ID: {user.id}"
    
    domains_text = ""
    if domains:
        domains_text = "\n\n📋 <b>Домены:</b>\n"
        for domain in domains:
            domains_text += f"• {domain.name} ({len(domain.urls)} страниц)\n"
    else:
        domains_text = "\n\n📋 <b>Доменов пока нет</b>"
    
    # Формируем username строку
    username_str = f"@{user.username}" if user.username else "не указан"
    
    await callback.message.edit_text(
        f"👤 <b>{display_name}</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Username: {username_str}\n"
        f"📱 Телефон: {user.phone or 'не указан'}\n"
        f"📅 Регистрация: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
        f"{domains_text}",
        parse_mode="HTML",
        reply_markup=get_client_actions_keyboard(client_id)
    )


@router.callback_query(F.data.startswith("client_domains_"))
async def callback_client_domains(callback: CallbackQuery):
    """Показать домены клиента с возможностью управления"""
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
    
    # Создаем клавиатуру с доменами
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    
    builder = InlineKeyboardBuilder()
    for domain in domains:
        status = "🟢" if domain.is_active else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {domain.name} ({len(domain.urls)} URL)",
                callback_data=f"domain_{domain.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data=f"client_{client_id}")
    )
    
    await callback.message.edit_text(
        "📋 <b>Домены клиента:</b>\n\n"
        "Выберите домен для управления:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
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
        "<b>Важно:</b> Клиент должен будет запустить бота командой /start для активации.",
        parse_mode="HTML"
    )
    await state.set_state(AddClientStates.waiting_for_identifier)


@router.message(AddClientStates.waiting_for_identifier)
async def process_client_identifier(message: Message, state: FSMContext):
    """Обработка username или телефона клиента"""
    identifier = message.text.strip()
    
    # Определяем, что это - username или телефон
    username = None
    phone = None
    
    if identifier.startswith('@') or not identifier.startswith('+'):
        # Это username
        username = identifier.lstrip('@')
    else:
        # Это телефон
        phone = identifier
    
    # Проверяем, не зарегистрирован ли уже этот пользователь
    existing_user = await db_manager.get_user_by_username_or_phone(identifier)
    if existing_user:
        if existing_user.role == "admin":
            await message.answer(
                "❌ Этот пользователь уже является администратором.\n\n"
                "Попробуйте другого или /cancel для отмены.",
                parse_mode="HTML"
            )
            return
        else:
            await message.answer(
                "✅ Этот пользователь уже зарегистрирован как клиент!\n\n"
                f"👤 Username: @{existing_user.username or 'не указан'}\n"
                f"📱 Телефон: {existing_user.phone or 'не указан'}\n\n"
                f"Вы можете привязать к нему домены через /add",
                parse_mode="HTML"
            )
            await state.clear()
            return
    
    # Проверяем, нет ли уже ожидающего приглашения
    existing_pending = await db_manager.get_pending_client_by_username_or_phone(username, phone)
    if existing_pending:
        await message.answer(
            "⚠️ Приглашение для этого клиента уже создано.\n\n"
            "Клиент должен запустить бота командой /start для активации.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Создаем ожидающего клиента
    try:
        pending_client = await db_manager.create_pending_client(
            username=username,
            phone=phone,
            invited_by=message.from_user.id
        )
        
        display_identifier = f"@{username}" if username else phone
        
        await message.answer(
            f"✅ <b>Приглашение создано!</b>\n\n"
            f"👤 Идентификатор: {display_identifier}\n\n"
            f"<b>Следующий шаг:</b>\n"
            f"Попросите клиента запустить бота командой /start\n\n"
            f"После этого он будет автоматически активирован, и вы сможете привязать к нему домены через /add",
            parse_mode="HTML"
        )
        
        logger.info(f"Admin {message.from_user.id} created pending client: {display_identifier}")
        
    except Exception as e:
        logger.error(f"Error creating pending client: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при создании приглашения:\n{str(e)}\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
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
        user = await db_manager.get_user_by_id(client_id)
        
        # Формируем отображаемое имя клиента
        if user:
            if user.first_name:
                display_name = user.first_name
                if user.last_name:
                    display_name += f" {user.last_name}"
            elif user.username:
                display_name = f"@{user.username}"
            else:
                display_name = f"ID:{user.id}"
        else:
            display_name = f"ID:{client_id}"
        
        await callback.message.edit_text(
            f"✅ <b>Домен привязан!</b>\n\n"
            f"🌐 Домен: <b>{domain.name}</b>\n"
            f"👤 Клиент: {display_name}\n\n"
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


@router.message(Command("restore_backup"))
async def cmd_restore_backup(message: Message, state: FSMContext):
    """Восстановление БД из бэкапа"""
    try:
        from pathlib import Path
        import os
        
        # Получаем список бэкапов
        backup_dir = Path("./backups")
        
        if not backup_dir.exists():
            await message.answer(
                "📂 Директория с бэкапами не найдена.\n\n"
                "Создайте хотя бы один бэкап через /backup",
                parse_mode="HTML"
            )
            return
        
        # Получаем все файлы бэкапов, отсортированные по дате (новые первые)
        backups = sorted(
            backup_dir.glob("siteheater_backup_*.sql.gz*"),
            key=os.path.getmtime,
            reverse=True
        )
        
        if not backups:
            await message.answer(
                "📂 Бэкапы не найдены.\n\n"
                "Создайте хотя бы один бэкап через /backup",
                parse_mode="HTML"
            )
            return
        
        # Формируем список бэкапов
        backup_list = []
        for i, backup in enumerate(backups[:20], 1):  # Показываем последние 20
            size_mb = backup.stat().st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            backup_list.append(
                f"{i}. <code>{backup.name}</code>\n"
                f"   📦 {size_mb:.2f} MB | 🕐 {mtime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        # Сохраняем список бэкапов в state
        await state.update_data(backups=[b.name for b in backups[:20]])
        await state.set_state(RestoreBackupStates.waiting_for_backup_selection)
        
        await message.answer(
            f"📂 <b>Доступные бэкапы</b> (последние 20):\n\n"
            f"{''.join([f'{b}\n' for b in backup_list])}\n\n"
            f"Введите номер бэкапа для восстановления (1-{len(backups[:20])}):",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error listing backups: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка при получении списка бэкапов:\n{str(e)}")


@router.message(RestoreBackupStates.waiting_for_backup_selection)
async def process_backup_selection(message: Message, state: FSMContext):
    """Обработка выбора бэкапа"""
    try:
        # Получаем номер бэкапа
        backup_number = int(message.text.strip())
        
        # Получаем список бэкапов из state
        data = await state.get_data()
        backups = data.get('backups', [])
        
        if backup_number < 1 or backup_number > len(backups):
            await message.answer(
                f"❌ Неверный номер. Введите число от 1 до {len(backups)}",
                parse_mode="HTML"
            )
            return
        
        selected_backup = backups[backup_number - 1]
        
        # Сохраняем выбранный бэкап
        await state.update_data(selected_backup=selected_backup)
        await state.set_state(RestoreBackupStates.waiting_for_confirmation)
        
        await message.answer(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"Вы собираетесь восстановить БД из бэкапа:\n"
            f"<code>{selected_backup}</code>\n\n"
            f"❗️ ВСЕ ТЕКУЩИЕ ДАННЫЕ БУДУТ УДАЛЕНЫ!\n\n"
            f"Для подтверждения введите: <b>YES</b>\n"
            f"Для отмены введите: <b>NO</b>",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.answer("❌ Введите корректный номер бэкапа")
    except Exception as e:
        logger.error(f"Error selecting backup: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


@router.message(RestoreBackupStates.waiting_for_confirmation)
async def process_restore_confirmation(message: Message, state: FSMContext):
    """Обработка подтверждения восстановления"""
    try:
        confirmation = message.text.strip().upper()
        
        if confirmation == "NO":
            await state.clear()
            await message.answer("❌ Восстановление отменено")
            return
        
        if confirmation != "YES":
            await message.answer(
                "⚠️ Введите <b>YES</b> для подтверждения или <b>NO</b> для отмены",
                parse_mode="HTML"
            )
            return
        
        # Получаем выбранный бэкап
        data = await state.get_data()
        selected_backup = data.get('selected_backup')
        
        if not selected_backup:
            await message.answer("❌ Ошибка: бэкап не выбран")
            await state.clear()
            return
        
        await message.answer(
            "🔄 <b>Начинаю восстановление...</b>\n\n"
            "⏳ Это может занять несколько минут.\n"
            "Бот временно будет недоступен.",
            parse_mode="HTML"
        )
        
        # Выполняем восстановление
        import subprocess
        
        result = subprocess.run(
            [
                "docker-compose", "-f", "docker-compose.secure.yml", "stop", "app"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        result = subprocess.run(
            [
                "docker-compose", "-f", "docker-compose.secure.yml", "run", "--rm",
                "--entrypoint", "/bin/sh",
                "backup",
                "-c", f"apk add --no-cache openssl bash && bash /scripts/restore_db.sh /app/backups/{selected_backup}"
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 минут
        )
        
        # Перезапускаем приложение
        subprocess.run(
            ["docker-compose", "-f", "docker-compose.secure.yml", "start", "app"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            await message.answer(
                "✅ <b>Восстановление завершено!</b>\n\n"
                f"📁 Восстановлено из: <code>{selected_backup}</code>\n\n"
                "🔄 Бот перезапущен с восстановленными данными.",
                parse_mode="HTML"
            )
            logger.info(f"Database restored from backup: {selected_backup}")
        else:
            await message.answer(
                "❌ <b>Ошибка восстановления!</b>\n\n"
                f"Проверьте логи сервера.\n\n"
                f"Stderr: {result.stderr[:500]}",
                parse_mode="HTML"
            )
            logger.error(f"Backup restore failed: {result.stderr}")
        
        await state.clear()
        
    except subprocess.TimeoutExpired:
        await message.answer("❌ Превышен таймаут восстановления")
        await state.clear()
    except Exception as e:
        logger.error(f"Error restoring backup: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


# Экспортируем роутер
__all__ = ['router']

