#!/bin/bash

# Скрипт для удаления автоматического бэкапа из cron

set -e

echo "🗑️  Удаление автоматического бэкапа"
echo "====================================="
echo ""

# Проверяем существует ли задача
if ! crontab -l 2>/dev/null | grep -q "docker-compose run --rm backup"; then
    echo "ℹ️  Задача бэкапа не найдена в crontab"
    echo ""
    echo "Текущие задачи cron:"
    crontab -l 2>/dev/null || echo "  (crontab пуст)"
    exit 0
fi

# Показываем текущую задачу
echo "📋 Текущая задача бэкапа:"
echo ""
crontab -l | grep "docker-compose run --rm backup"
echo ""

read -p "Удалить эту задачу? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Отменено"
    exit 1
fi

# Удаляем задачу
crontab -l | grep -v "docker-compose run --rm backup" | crontab -

echo ""
echo "✅ Задача удалена из crontab"
echo ""
echo "📋 Оставшиеся задачи cron:"
crontab -l 2>/dev/null || echo "  (crontab пуст)"
echo ""
echo "✨ Готово!"

