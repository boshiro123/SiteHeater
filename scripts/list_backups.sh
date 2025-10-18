#!/bin/bash

# Скрипт для просмотра списка бэкапов с подробной информацией

set -e

echo "📋 Список бэкапов"
echo "================="
echo ""

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

# Локальные бэкапы
echo "💾 Локальные бэкапы (на сервере):"
echo ""

BACKUPS=$(docker-compose -f docker-compose.secure.yml run --rm backup sh -c 'ls -lh /app/backups/*.sql.gz* 2>/dev/null || echo ""')

if [ -z "$BACKUPS" ]; then
    echo "   ❌ Локальных бэкапов не найдено"
else
    echo "$BACKUPS" | while IFS= read -r line; do
        if [[ "$line" =~ ^-.*\.sql\.gz ]]; then
            # Извлекаем информацию
            size=$(echo "$line" | awk '{print $5}')
            date=$(echo "$line" | awk '{print $6, $7, $8}')
            filename=$(echo "$line" | awk '{print $9}')
            
            # Проверяем зашифрован ли
            if [[ "$filename" == *.enc ]]; then
                status="🔐 зашифрован"
            else
                status="📦 не зашифрован"
            fi
            
            echo "   • $(basename $filename)"
            echo "     Размер: $size | Дата: $date | $status"
        fi
    done
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Статистика
echo "📊 Статистика:"
echo ""

# Количество бэкапов
BACKUP_COUNT=$(docker-compose -f docker-compose.secure.yml run --rm backup sh -c 'ls -1 /app/backups/*.sql.gz* 2>/dev/null | wc -l' | tr -d ' ')
echo "   Всего бэкапов: $BACKUP_COUNT"

# Общий размер
TOTAL_SIZE=$(docker-compose -f docker-compose.secure.yml run --rm backup sh -c 'du -sh /app/backups 2>/dev/null | cut -f1' || echo "0")
echo "   Общий размер: $TOTAL_SIZE"

# Последний бэкап
LAST_BACKUP=$(docker-compose -f docker-compose.secure.yml run --rm backup sh -c 'ls -t /app/backups/*.sql.gz* 2>/dev/null | head -1' | tr -d '\r')
if [ -n "$LAST_BACKUP" ]; then
    echo "   Последний бэкап: $(basename $LAST_BACKUP)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# GitHub бэкапы
echo "☁️  Проверка GitHub бэкапов..."
echo ""

# Проверяем .env
if [ ! -f .env ]; then
    echo "   ⚠️  Файл .env не найден"
else
    GITHUB_REPO=$(grep BACKUP_GITHUB_REPO .env | cut -d= -f2)
    GITHUB_BRANCH=$(grep BACKUP_GITHUB_BRANCH .env | cut -d= -f2)
    
    if [ -n "$GITHUB_REPO" ]; then
        echo "   📦 Репозиторий: https://github.com/${GITHUB_REPO}"
        echo "   🌿 Ветка: ${GITHUB_BRANCH:-main}"
        echo ""
        echo "   Для просмотра откройте:"
        echo "   https://github.com/${GITHUB_REPO}/tree/${GITHUB_BRANCH:-main}"
    else
        echo "   ⚠️  GitHub репозиторий не настроен"
        echo ""
        echo "   Настройте в файле .env:"
        echo "   BACKUP_GITHUB_REPO=username/repo"
        echo "   BACKUP_GITHUB_TOKEN=ghp_xxxxxxxxxxxx"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Команды
echo "📝 Полезные команды:"
echo ""
echo "   Создать новый бэкап:"
echo "   $ docker-compose -f docker-compose.secure.yml run --rm backup"
echo ""
echo "   Восстановить из бэкапа:"
echo "   $ bash scripts/quick_restore.sh"
echo ""
echo "   Удалить старые бэкапы (>7 дней):"
echo "   $ docker-compose -f docker-compose.secure.yml run --rm backup find /app/backups -name '*.sql.gz*' -mtime +7 -delete"
echo ""
echo "   Скачать бэкап на локальную машину:"
echo "   $ docker cp siteheater_backup:/app/backups/backup_file.sql.gz.enc ./"
echo ""

echo "✨ Готово!"

