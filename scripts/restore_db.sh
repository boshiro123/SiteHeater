#!/bin/bash

# Скрипт восстановления базы данных из бэкапа
# Использование: ./restore_db.sh <backup_file>

set -e

# === КОНФИГУРАЦИЯ ===

if [ -z "$1" ]; then
    echo "❌ Использование: $0 <backup_file>"
    echo "Пример: $0 siteheater_backup_20250112_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

# PostgreSQL настройки
PGUSER="${POSTGRES_USER:-siteheater}"
PGPASSWORD="${POSTGRES_PASSWORD:-siteheater_password}"
PGDATABASE="${POSTGRES_DB:-siteheater}"
PGHOST="${POSTGRES_HOST:-postgres}"

# === ФУНКЦИИ ===

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

# === ПРОВЕРКА ФАЙЛА ===

if [ ! -f "$BACKUP_FILE" ]; then
    error_exit "Файл бэкапа не найден: $BACKUP_FILE"
fi

log "📦 Найден файл бэкапа: $BACKUP_FILE"

# === РАСШИФРОВКА (если зашифрован) ===

if [[ "$BACKUP_FILE" == *.enc ]]; then
    if [ -z "$BACKUP_ENCRYPTION_KEY" ]; then
        error_exit "Требуется BACKUP_ENCRYPTION_KEY для расшифровки"
    fi
    
    log "🔐 Расшифровка бэкапа..."
    
    DECRYPTED_FILE="${BACKUP_FILE%.enc}"
    
    if openssl enc -aes-256-cbc -d -pbkdf2 -in "$BACKUP_FILE" -out "$DECRYPTED_FILE" -k "$BACKUP_ENCRYPTION_KEY"; then
        BACKUP_FILE="$DECRYPTED_FILE"
        log "✅ Бэкап расшифрован"
    else
        error_exit "Не удалось расшифровать бэкап"
    fi
fi

# === ПОДТВЕРЖДЕНИЕ ===

echo ""
echo "⚠️  ========================================= ⚠️"
echo "⚠️  ВНИМАНИЕ! Восстановление базы данных    ⚠️"
echo "⚠️  ========================================= ⚠️"
echo ""
echo "Это действие заменит текущую базу данных на:"
echo "  Файл: $BACKUP_FILE"
echo "  База: $PGDATABASE@$PGHOST"
echo ""
read -p "Вы уверены? (введите YES для подтверждения): " CONFIRM

if [ "$CONFIRM" != "YES" ]; then
    log "❌ Восстановление отменено"
    exit 0
fi

# === ВОССТАНОВЛЕНИЕ ===

log "🔄 Восстановление базы данных..."

# Экспорт переменных
export PGPASSWORD

# Остановка активных подключений
log "⏸️  Завершение активных подключений..."
psql -h "$PGHOST" -U "$PGUSER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$PGDATABASE' AND pid <> pg_backend_pid();" || true

# Удаление существующей базы
log "🗑️  Удаление существующей базы..."
dropdb -h "$PGHOST" -U "$PGUSER" "$PGDATABASE" --if-exists || error_exit "Не удалось удалить базу данных"

# Создание новой базы
log "📦 Создание новой базы..."
createdb -h "$PGHOST" -U "$PGUSER" "$PGDATABASE" || error_exit "Не удалось создать базу данных"

# Восстановление из бэкапа
log "⏳ Восстановление данных из бэкапа..."

if gunzip -c "$BACKUP_FILE" | psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE"; then
    log "✅ База данных успешно восстановлена!"
    log "🎉 Восстановление завершено"
else
    error_exit "Не удалось восстановить базу данных"
fi

# Очистка временных файлов
if [[ "$BACKUP_FILE" == *".dec" ]]; then
    rm -f "$BACKUP_FILE"
    log "🧹 Временные файлы удалены"
fi

log "✨ Готово! Перезапустите приложение для применения изменений."

