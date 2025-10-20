#!/bin/bash

# Скрипт настройки автоматических бэкапов каждый час
# Использование: ./setup_hourly_backup.sh

set -e

echo "⚙️  Настройка автоматических бэкапов"
echo "===================================="
echo ""

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Делаем скрипт бэкапа исполняемым
chmod +x "$PROJECT_DIR/scripts/auto_backup_with_notification.sh"

# Файл для логов
LOG_FILE="$PROJECT_DIR/backups/auto_backup.log"
mkdir -p "$PROJECT_DIR/backups"

# Создаем команду для cron (каждый час)
CRON_COMMAND="0 * * * * cd ${PROJECT_DIR} && bash ${PROJECT_DIR}/scripts/auto_backup_with_notification.sh >> ${LOG_FILE} 2>&1"

# Проверяем существует ли уже такая задача
if crontab -l 2>/dev/null | grep -q "auto_backup_with_notification.sh"; then
    echo "⚠️  Задача автоматического бэкапа уже существует в crontab"
    echo ""
    read -p "Пересоздать задачу? (y/n): " answer
    
    if [ "$answer" != "y" ]; then
        echo "❌ Отменено"
        exit 0
    fi
    
    # Удаляем старую задачу
    crontab -l 2>/dev/null | grep -v "auto_backup_with_notification.sh" | crontab -
    echo "🗑️  Старая задача удалена"
fi

# Добавляем новую задачу
(crontab -l 2>/dev/null; echo "${CRON_COMMAND}") | crontab -

echo ""
echo "✅ Автоматический бэкап настроен!"
echo ""
echo "📋 Текущие задачи cron:"
crontab -l | grep "auto_backup_with_notification.sh" || echo "  (нет задач)"
echo ""
echo "⏰ Расписание: Каждый час (в 00 минут)"
echo "📝 Логи будут сохраняться в: ${LOG_FILE}"
echo ""
echo "🧪 Для тестового запуска бэкапа выполните:"
echo "   bash $PROJECT_DIR/scripts/auto_backup_with_notification.sh"
echo ""
echo "📖 Для просмотра логов:"
echo "   tail -f ${LOG_FILE}"
echo ""
echo "🛑 Для остановки автоматических бэкапов:"
echo "   bash $PROJECT_DIR/scripts/stop_hourly_backup.sh"
echo ""
echo "✨ Настройка завершена!"

