#!/bin/bash

# Скрипт для настройки автоматического бэкапа через cron

set -e

echo "🔧 Настройка автоматического бэкапа"
echo "===================================="
echo ""

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${HOME}/siteheater-backup.log"

echo "📂 Директория проекта: ${PROJECT_DIR}"
echo "📝 Файл логов: ${LOG_FILE}"
echo ""

# Выбор частоты бэкапов
echo "Выберите частоту бэкапов:"
echo "1) Каждый час (0 * * * *)"
echo "2) Каждые 2 часа (0 */2 * * *)"
echo "3) Каждые 6 часов (0 */6 * * *)"
echo "4) Каждые 12 часов (0 */12 * * *)"
echo "5) Раз в день в 02:00 (0 2 * * *)"
echo "6) Раз в день в 03:00 (0 3 * * *)"
echo ""
read -p "Введите номер (1-6): " choice

case $choice in
    1)
        CRON_SCHEDULE="0 * * * *"
        DESCRIPTION="каждый час"
        ;;
    2)
        CRON_SCHEDULE="0 */2 * * *"
        DESCRIPTION="каждые 2 часа"
        ;;
    3)
        CRON_SCHEDULE="0 */6 * * *"
        DESCRIPTION="каждые 6 часов"
        ;;
    4)
        CRON_SCHEDULE="0 */12 * * *"
        DESCRIPTION="каждые 12 часов"
        ;;
    5)
        CRON_SCHEDULE="0 2 * * *"
        DESCRIPTION="каждый день в 02:00"
        ;;
    6)
        CRON_SCHEDULE="0 3 * * *"
        DESCRIPTION="каждый день в 03:00"
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

echo ""
echo "✅ Выбрано: ${DESCRIPTION}"
echo ""

# Создаем команду для cron
CRON_COMMAND="${CRON_SCHEDULE} cd ${PROJECT_DIR} && /usr/bin/docker-compose -f docker-compose.secure.yml run --rm backup >> ${LOG_FILE} 2>&1"

# Проверяем существует ли уже такая задача
if crontab -l 2>/dev/null | grep -q "docker-compose run --rm backup"; then
    echo "⚠️  Задача бэкапа уже существует в crontab"
    echo ""
    crontab -l | grep "docker-compose run --rm backup"
    echo ""
    read -p "Удалить старую и добавить новую? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Отменено"
        exit 1
    fi
    # Удаляем старую задачу
    crontab -l | grep -v "docker-compose run --rm backup" | crontab -
    echo "✅ Старая задача удалена"
fi

# Добавляем новую задачу
(crontab -l 2>/dev/null; echo "${CRON_COMMAND}") | crontab -

echo ""
echo "✅ Задача добавлена в crontab"
echo ""
echo "📋 Текущие задачи cron:"
crontab -l | grep "docker-compose run --rm backup" || echo "  (нет задач)"
echo ""
echo "📊 Расписание: ${DESCRIPTION}"
echo "📝 Логи будут сохраняться в: ${LOG_FILE}"
echo ""
echo "🧪 Для тестового запуска бэкапа выполните:"
echo "   cd ${PROJECT_DIR} && make backup"
echo ""
echo "📖 Для просмотра логов:"
echo "   tail -f ${LOG_FILE}"
echo ""
echo "✨ Настройка завершена!"

