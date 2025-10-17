#!/bin/bash

# Скрипт для быстрого восстановления БД из бэкапа

set -e

echo "🔄 Восстановление базы данных"
echo "=============================="
echo ""

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

# Проверяем наличие бэкапов
echo "📋 Доступные бэкапы:"
echo ""

# Получаем список бэкапов
BACKUPS=$(docker-compose run --rm backup ls -1 /app/backups/ 2>/dev/null | grep -E '\.sql\.gz(\.enc)?$' | sort -r || echo "")

if [ -z "$BACKUPS" ]; then
    echo "❌ Бэкапы не найдены!"
    echo ""
    echo "Создайте бэкап командой:"
    echo "  docker-compose run --rm backup"
    exit 1
fi

# Показываем список с номерами
i=1
declare -A BACKUP_MAP
while IFS= read -r backup; do
    if [ -n "$backup" ]; then
        echo "$i) $backup"
        BACKUP_MAP[$i]="$backup"
        ((i++))
    fi
done <<< "$BACKUPS"

echo ""
read -p "Выберите номер бэкапа для восстановления: " choice

# Проверяем выбор
if [ -z "${BACKUP_MAP[$choice]}" ]; then
    echo "❌ Неверный выбор"
    exit 1
fi

BACKUP_FILE="${BACKUP_MAP[$choice]}"

echo ""
echo "⚠️  ВНИМАНИЕ! Восстановление БД удалит ВСЕ текущие данные!"
echo "Файл: ${BACKUP_FILE}"
echo ""
read -p "Вы уверены? Введите 'YES' для подтверждения: " confirm

if [ "$confirm" != "YES" ]; then
    echo "❌ Отменено"
    exit 1
fi

echo ""
echo "🔄 Начинаем восстановление..."
echo ""

# Остановка приложения
echo "1️⃣ Остановка приложения..."
docker-compose stop app
echo "   ✅ Приложение остановлено"
echo ""

# Восстановление БД
echo "2️⃣ Восстановление базы данных..."
echo ""

if docker-compose run --rm backup /bin/bash /scripts/restore_db.sh "/app/backups/${BACKUP_FILE}"; then
    echo ""
    echo "   ✅ База данных восстановлена"
else
    echo ""
    echo "   ❌ Ошибка при восстановлении!"
    echo ""
    echo "Попробуйте восстановить вручную:"
    echo "  docker-compose run --rm backup /bin/bash /scripts/restore_db.sh /app/backups/${BACKUP_FILE}"
    exit 1
fi

echo ""

# Запуск приложения
echo "3️⃣ Запуск приложения..."
docker-compose start app
echo "   ✅ Приложение запущено"
echo ""

# Ожидание запуска
echo "⏳ Ожидание запуска (5 секунд)..."
sleep 5

# Проверка логов
echo ""
echo "📊 Последние логи приложения:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose logs --tail=20 app
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✨ Восстановление завершено!"
echo ""
echo "Проверьте работу бота:"
echo "  1. Откройте Telegram бот"
echo "  2. Отправьте /start"
echo "  3. Проверьте список доменов: /domains"
echo ""
echo "Для просмотра полных логов:"
echo "  docker-compose logs -f app"

