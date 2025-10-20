#!/bin/bash

# Скрипт автоматического бэкапа с уведомлением в Telegram
# Использование: ./auto_backup_with_notification.sh

set -e

# Директория проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Загрузка переменных окружения
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Создание бэкапа
echo "[$(date +'%Y-%m-%d %H:%M:%S')] 💾 Создание бэкапа..."

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="siteheater_backup_${TIMESTAMP}.sql.gz"

# Выполняем бэкап через docker exec
docker exec siteheater_postgres sh -c "PGPASSWORD='${POSTGRES_PASSWORD}' pg_dump -U ${POSTGRES_USER} -d ${POSTGRES_DB} | gzip" > "$BACKUP_DIR/$BACKUP_FILE"

if [ $? -eq 0 ] && [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ Бэкап создан: $BACKUP_FILE ($BACKUP_SIZE)"
    
    # Получение ID всех админов из БД и отправка уведомлений
    ADMIN_IDS=$(docker exec siteheater_postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT id FROM users WHERE role = 'admin';" | tr -d ' ')
    
    MESSAGE="💾 <b>Автоматический бэкап создан</b>%0A%0A📁 Файл: <code>${BACKUP_FILE}</code>%0A📦 Размер: <b>${BACKUP_SIZE}</b>%0A🕐 Время: <b>$(date +'%Y-%m-%d %H:%M:%S')</b>%0A%0A✅ Бэкап сохранен в <code>./backups/</code>"
    
    for ADMIN_ID in $ADMIN_IDS; do
        if [ ! -z "$ADMIN_ID" ]; then
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${ADMIN_ID}" \
                -d "text=${MESSAGE}" \
                -d "parse_mode=HTML" > /dev/null 2>&1
        fi
    done
    
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] 📤 Уведомления отправлены админам"
    
    # Очистка старых бэкапов (старше 7 дней)
    find "$BACKUP_DIR" -name "siteheater_backup_*.sql.gz*" -type f -mtime +7 -delete
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] 🧹 Старые бэкапы очищены"
    
else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ❌ Ошибка создания бэкапа"
    
    # Отправка уведомления об ошибке
    ADMIN_IDS=$(docker exec siteheater_postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT id FROM users WHERE role = 'admin';" | tr -d ' ')
    
    ERROR_MESSAGE="❌ <b>Ошибка автоматического бэкапа</b>%0A%0A🕐 Время: $(date +'%Y-%m-%d %H:%M:%S')%0A⚠️ Проверьте логи сервера"
    
    for ADMIN_ID in $ADMIN_IDS; do
        if [ ! -z "$ADMIN_ID" ]; then
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${ADMIN_ID}" \
                -d "text=${ERROR_MESSAGE}" \
                -d "parse_mode=HTML" > /dev/null 2>&1
        fi
    done
    
    exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✨ Бэкап завершен"

