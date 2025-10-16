#!/bin/bash

# Скрипт автоматического бэкапа PostgreSQL и отправки на GitHub
# Использование: ./backup_db.sh

set -e

# === КОНФИГУРАЦИЯ ===
BACKUP_DIR="/app/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="siteheater_backup_${TIMESTAMP}.sql.gz"
KEEP_DAYS=7  # Хранить бэкапы за последние N дней

# GitHub настройки (загружаются из переменных окружения)
GITHUB_REPO="${BACKUP_GITHUB_REPO}"  # Например: username/siteheater-backups
GITHUB_TOKEN="${BACKUP_GITHUB_TOKEN}"
GITHUB_BRANCH="${BACKUP_GITHUB_BRANCH:-main}"

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

# Создание директории для бэкапов
mkdir -p "$BACKUP_DIR"

# === СОЗДАНИЕ БЭКАПА ===

log "🔄 Создание бэкапа базы данных..."

# Экспорт переменных для pg_dump
export PGPASSWORD

# Создание бэкапа и сжатие
if pg_dump -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" | gzip > "$BACKUP_DIR/$BACKUP_FILE"; then
    log "✅ Бэкап создан: $BACKUP_FILE"
    BACKUP_SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    log "📦 Размер: $BACKUP_SIZE"
else
    error_exit "Не удалось создать бэкап базы данных"
fi

# === ШИФРОВАНИЕ (опционально) ===

if [ -n "$BACKUP_ENCRYPTION_KEY" ]; then
    log "🔐 Шифрование бэкапа..."
    
    ENCRYPTED_FILE="$BACKUP_DIR/${BACKUP_FILE}.enc"
    
    if openssl enc -aes-256-cbc -salt -pbkdf2 -in "$BACKUP_DIR/$BACKUP_FILE" -out "$ENCRYPTED_FILE" -k "$BACKUP_ENCRYPTION_KEY"; then
        rm "$BACKUP_DIR/$BACKUP_FILE"
        BACKUP_FILE="${BACKUP_FILE}.enc"
        log "✅ Бэкап зашифрован"
    else
        error_exit "Не удалось зашифровать бэкап"
    fi
fi

# === ОТПРАВКА НА GITHUB ===

if [ -n "$GITHUB_REPO" ] && [ -n "$GITHUB_TOKEN" ]; then
    log "📤 Отправка бэкапа на GitHub..."
    
    # Клонирование репозитория или обновление
    REPO_DIR="$BACKUP_DIR/repo"
    
    if [ ! -d "$REPO_DIR/.git" ]; then
        log "📦 Клонирование репозитория..."
        git clone "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" "$REPO_DIR" || error_exit "Не удалось клонировать репозиторий"
    else
        log "🔄 Обновление репозитория..."
        cd "$REPO_DIR"
        git pull origin "$GITHUB_BRANCH" || log "⚠️ Не удалось обновить репозиторий"
    fi
    
    # Копирование бэкапа в репозиторий
    cp "$BACKUP_DIR/$BACKUP_FILE" "$REPO_DIR/"
    
    # Коммит и отправка
    cd "$REPO_DIR"
    git config user.name "SiteHeater Backup Bot"
    git config user.email "backup@siteheater.local"
    git add "$BACKUP_FILE"
    git commit -m "Автоматический бэкап: $(date +'%Y-%m-%d %H:%M:%S')" || log "⚠️ Нет изменений для коммита"
    
    if git push origin "$GITHUB_BRANCH"; then
        log "✅ Бэкап отправлен на GitHub"
    else
        error_exit "Не удалось отправить бэкап на GitHub"
    fi
else
    log "⚠️ GitHub не настроен, бэкап сохранен локально"
fi

# === ОЧИСТКА СТАРЫХ БЭКАПОВ ===

log "🧹 Очистка старых бэкапов (старше $KEEP_DAYS дней)..."

# Локальные бэкапы
find "$BACKUP_DIR" -name "siteheater_backup_*.sql.gz*" -type f -mtime +$KEEP_DAYS -delete

# Бэкапы в GitHub репозитории
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR"
    
    # Удаление файлов старше N дней
    OLD_FILES=$(find . -name "siteheater_backup_*.sql.gz*" -type f -mtime +$KEEP_DAYS)
    
    if [ -n "$OLD_FILES" ]; then
        echo "$OLD_FILES" | while read file; do
            git rm "$file"
            log "🗑️ Удален старый бэкап: $file"
        done
        
        git commit -m "Автоматическая очистка старых бэкапов" || true
        git push origin "$GITHUB_BRANCH" || log "⚠️ Не удалось отправить изменения"
    fi
fi

log "✨ Бэкап завершен успешно!"

