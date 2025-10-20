#!/bin/bash

# Скрипт остановки автоматических бэкапов
# Использование: ./stop_hourly_backup.sh

set -e

echo "🛑 Остановка автоматических бэкапов"
echo "==================================="
echo ""

# Проверяем существует ли задача
if ! crontab -l 2>/dev/null | grep -q "auto_backup_with_notification.sh"; then
    echo "⚠️  Задача автоматического бэкапа не найдена в crontab"
    echo ""
    exit 0
fi

# Удаляем задачу
crontab -l 2>/dev/null | grep -v "auto_backup_with_notification.sh" | crontab -

echo "✅ Задача автоматического бэкапа удалена из crontab"
echo ""
echo "📋 Оставшиеся задачи cron:"
crontab -l 2>/dev/null || echo "  (нет задач)"
echo ""
echo "✨ Готово!"

