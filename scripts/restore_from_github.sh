#!/bin/bash

# Скрипт для восстановления БД из бэкапа на GitHub

set -e

echo "☁️  Восстановление из GitHub"
echo "============================"
echo ""

# Определяем директорию проекта
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"

# Проверяем .env
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

# Получаем настройки GitHub
GITHUB_REPO=$(grep BACKUP_GITHUB_REPO .env | cut -d= -f2)
GITHUB_BRANCH=$(grep BACKUP_GITHUB_BRANCH .env | cut -d= -f2)

if [ -z "$GITHUB_REPO" ]; then
    echo "❌ BACKUP_GITHUB_REPO не настроен в .env"
    exit 1
fi

echo "📦 GitHub репозиторий: https://github.com/${GITHUB_REPO}"
echo "🌿 Ветка: ${GITHUB_BRANCH:-main}"
echo ""

# Создаем временную директорию
TEMP_DIR="/tmp/siteheater_backups_$$"
mkdir -p "$TEMP_DIR"

echo "📥 Клонирование репозитория с бэкапами..."
echo ""

# Клонируем репозиторий
if ! git clone -b "${GITHUB_BRANCH:-main}" "https://github.com/${GITHUB_REPO}.git" "$TEMP_DIR" 2>/dev/null; then
    echo "❌ Не удалось клонировать репозиторий"
    echo ""
    echo "Возможные причины:"
    echo "  1. Репозиторий не существует"
    echo "  2. Нет прав доступа (приватный репозиторий)"
    echo "  3. Неправильное имя репозитория в .env"
    echo ""
    echo "Попробуйте клонировать вручную:"
    echo "  git clone https://github.com/${GITHUB_REPO}.git"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "✅ Репозиторий клонирован"
echo ""

# Получаем список бэкапов
echo "📋 Доступные бэкапы на GitHub:"
echo ""

cd "$TEMP_DIR"
BACKUPS=$(ls -1 *.sql.gz* 2>/dev/null | sort -r || echo "")

if [ -z "$BACKUPS" ]; then
    echo "❌ Бэкапы не найдены в репозитории!"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Показываем список с номерами
i=1
declare -A BACKUP_MAP
while IFS= read -r backup; do
    if [ -n "$backup" ]; then
        size=$(du -h "$backup" 2>/dev/null | cut -f1)
        date=$(stat -c '%y' "$backup" 2>/dev/null | cut -d' ' -f1 || stat -f '%Sm' -t '%Y-%m-%d' "$backup" 2>/dev/null)
        echo "$i) $backup (Размер: $size, Дата: $date)"
        BACKUP_MAP[$i]="$backup"
        ((i++))
    fi
done <<< "$BACKUPS"

echo ""
read -p "Выберите номер бэкапа для восстановления: " choice

# Проверяем выбор
if [ -z "${BACKUP_MAP[$choice]}" ]; then
    echo "❌ Неверный выбор"
    rm -rf "$TEMP_DIR"
    exit 1
fi

BACKUP_FILE="${BACKUP_MAP[$choice]}"

echo ""
echo "⚠️  ВНИМАНИЕ! Восстановление БД удалит ВСЕ текущие данные!"
echo "Файл: ${BACKUP_FILE}"
echo "Источник: GitHub (${GITHUB_REPO})"
echo ""
read -p "Вы уверены? Введите 'YES' для подтверждения: " confirm

if [ "$confirm" != "YES" ]; then
    echo "❌ Отменено"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo ""
echo "🔄 Начинаем восстановление из GitHub..."
echo ""

# Копируем бэкап в проект
echo "1️⃣ Копирование бэкапа с GitHub..."
cp "${BACKUP_FILE}" "${PROJECT_DIR}/"
echo "   ✅ Бэкап скопирован"
echo ""

# Очищаем временную директорию
rm -rf "$TEMP_DIR"

# Переходим в директорию проекта
cd "${PROJECT_DIR}"

# Копируем бэкап в Docker volume
echo "2️⃣ Импорт бэкапа в Docker volume..."

# Используем простой alpine контейнер для копирования в volume
docker run --rm -v siteheater_backup_data:/app/backups -v "${PROJECT_DIR}/${BACKUP_FILE}:/tmp/${BACKUP_FILE}" alpine cp /tmp/${BACKUP_FILE} /app/backups/${BACKUP_FILE}

echo "   ✅ Бэкап импортирован"
echo ""

# Остановка приложения
echo "3️⃣ Остановка приложения..."
docker-compose stop app
echo "   ✅ Приложение остановлено"
echo ""

# Восстановление БД
echo "4️⃣ Восстановление базы данных..."
echo ""

if docker-compose run --rm backup /bin/bash /scripts/restore_db.sh "/app/backups/${BACKUP_FILE}"; then
    echo ""
    echo "   ✅ База данных восстановлена"
else
    echo ""
    echo "   ❌ Ошибка при восстановлении!"
    rm -f "${PROJECT_DIR}/${BACKUP_FILE}"
    exit 1
fi

echo ""

# Удаляем локальную копию бэкапа
rm -f "${PROJECT_DIR}/${BACKUP_FILE}"

# Запуск приложения
echo "5️⃣ Запуск приложения..."
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

echo "✨ Восстановление из GitHub завершено!"
echo ""
echo "Проверьте работу бота:"
echo "  1. Откройте Telegram бот"
echo "  2. Отправьте /start"
echo "  3. Проверьте список доменов: /domains"
echo ""
echo "Для просмотра полных логов:"
echo "  docker-compose logs -f app"

