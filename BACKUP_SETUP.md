# 🔄 Настройка автоматических бэкапов базы данных

## 📋 Содержание

- [Подготовка](#подготовка)
- [Настройка GitHub](#настройка-github)
- [Настройка переменных окружения](#настройка-переменных-окружения)
- [Запуск бэкапов](#запуск-бэкапов)
- [Автоматизация](#автоматизация)
- [Восстановление из бэкапа](#восстановление-из-бэкапа)

---

## 🔧 Подготовка

### 1. Создайте приватный репозиторий на GitHub

**Важно:** Репозиторий должен быть **приватным**!

```bash
# На GitHub:
# 1. Зайдите на https://github.com/new
# 2. Название: например "siteheater-backups"
# 3. Выберите: ✅ Private
# 4. Инициализируйте с README
# 5. Нажмите "Create repository"
```

### 2. Создайте Personal Access Token

1. Зайдите в: **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Нажмите: **Generate new token (classic)**
3. Настройки:
   - **Note**: `SiteHeater Backups`
   - **Expiration**: `No expiration` (или выберите срок)
   - **Scopes**: ✅ `repo` (full control)
4. Нажмите **Generate token**
5. **Сохраните токен** (он больше не будет показан!)

---

## ⚙️ Настройка GitHub

### 1. Добавьте переменные в `.env` файл

```bash
# === НАСТРОЙКИ БЭКАПА ===

# GitHub репозиторий (формат: username/repo-name)
BACKUP_GITHUB_REPO=your-username/siteheater-backups

# Personal Access Token от GitHub
BACKUP_GITHUB_TOKEN=ghp_ваш_токен_здесь

# Ветка для бэкапов (по умолчанию: main)
BACKUP_GITHUB_BRANCH=main

# Ключ шифрования (опционально, но рекомендуется!)
# Используйте сложный пароль
BACKUP_ENCRYPTION_KEY=your-super-secret-encryption-key-here
```

### 2. Сделайте скрипты исполняемыми

```bash
chmod +x scripts/backup_db.sh
chmod +x scripts/restore_db.sh
```

---

## 🚀 Запуск бэкапов

### Ручной запуск бэкапа

```bash
# Запуск контейнера бэкапа
docker-compose run --rm backup

# Или через make (если есть Makefile)
make backup
```

### Проверка бэкапов

```bash
# Локальные бэкапы
docker-compose exec backup ls -lh /app/backups/

# Бэкапы на GitHub
# Зайдите в ваш репозиторий: https://github.com/username/siteheater-backups
```

---

## ⏰ Автоматизация

### Вариант 1: Cron на хосте

Добавьте в crontab:

```bash
# Редактируем crontab
crontab -e

# Добавляем задание (каждый день в 03:00)
0 3 * * * cd /path/to/SiteHeater && docker-compose run --rm backup >> /var/log/siteheater-backup.log 2>&1
```

**Примеры расписаний:**

```bash
# Каждые 6 часов
0 */6 * * * cd /path/to/SiteHeater && docker-compose run --rm backup

# Каждый день в 03:00
0 3 * * * cd /path/to/SiteHeater && docker-compose run --rm backup

# Каждое воскресенье в 02:00
0 2 * * 0 cd /path/to/SiteHeater && docker-compose run --rm backup
```

### Вариант 2: systemd timer

Создайте файл `/etc/systemd/system/siteheater-backup.service`:

```ini
[Unit]
Description=SiteHeater Database Backup
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/path/to/SiteHeater
ExecStart=/usr/bin/docker-compose run --rm backup

[Install]
WantedBy=multi-user.target
```

Создайте файл `/etc/systemd/system/siteheater-backup.timer`:

```ini
[Unit]
Description=SiteHeater Backup Timer

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Активируйте:

```bash
sudo systemctl daemon-reload
sudo systemctl enable siteheater-backup.timer
sudo systemctl start siteheater-backup.timer
sudo systemctl status siteheater-backup.timer
```

### Вариант 3: GitHub Actions (альтернатива)

Создайте файл `.github/workflows/backup.yml` в репозитории бэкапов:

```yaml
name: Database Backup Reminder

on:
  schedule:
    - cron: "0 3 * * *" # Каждый день в 03:00 UTC
  workflow_dispatch: # Ручной запуск

jobs:
  remind:
    runs-on: ubuntu-latest
    steps:
      - name: Send reminder
        run: |
          echo "Напоминание: Запустите бэкап на вашем сервере!"
          # Здесь можно добавить отправку уведомления
```

---

## 🔄 Восстановление из бэкапа

### 1. Найдите нужный бэкап

```bash
# Локально
docker-compose exec backup ls -lh /app/backups/

# Или скачайте с GitHub
# Зайдите в репозиторий и скачайте нужный файл
```

### 2. Восстановите базу данных

**⚠️ ВНИМАНИЕ:** Это удалит все текущие данные!

```bash
# Остановите приложение
docker-compose stop app

# Скопируйте бэкап в контейнер (если скачали с GitHub)
docker cp siteheater_backup_20250112_120000.sql.gz siteheater_postgres:/tmp/

# Запустите восстановление
docker-compose run --rm -e BACKUP_FILE=/app/backups/siteheater_backup_20250112_120000.sql.gz backup /bin/bash /scripts/restore_db.sh /app/backups/siteheater_backup_20250112_120000.sql.gz

# Или восстановите напрямую в postgres контейнере
docker exec -i siteheater_postgres pg_restore -U siteheater -d siteheater -v < backup.sql

# Перезапустите приложение
docker-compose start app
```

### 3. Восстановление из зашифрованного бэкапа

```bash
# Убедитесь, что в .env указан BACKUP_ENCRYPTION_KEY
docker-compose run --rm -e BACKUP_ENCRYPTION_KEY=your-key backup /bin/bash /scripts/restore_db.sh /app/backups/siteheater_backup_20250112_120000.sql.gz.enc
```

---

## 🔒 Безопасность

### Рекомендации:

1. **✅ Всегда используйте приватный репозиторий**
2. **✅ Включите шифрование** (BACKUP_ENCRYPTION_KEY)
3. **✅ Ротация токенов** каждые 3-6 месяцев
4. **✅ Храните ключи в безопасном месте** (password manager)
5. **✅ Регулярно проверяйте бэкапы** (делайте тестовое восстановление)

### Что шифруется:

- ✅ Дамп базы данных
- ✅ Все персональные данные пользователей
- ✅ Токены и пароли из БД

### Что НЕ шифруется:

- ⚠️ Имя файла бэкапа (видна дата создания)

---

## 📊 Мониторинг

### Проверка статуса бэкапов

```bash
# Последний бэкап
docker-compose exec backup ls -lht /app/backups/ | head -n 2

# Размер всех бэкапов
docker-compose exec backup du -sh /app/backups/

# Логи последнего бэкапа
docker-compose logs backup
```

### Тестирование восстановления

Рекомендуется раз в месяц проверять, что бэкапы корректны:

```bash
# Создайте тестовую базу
# Восстановите в неё последний бэкап
# Проверьте данные
```

---

## ❓ Troubleshooting

### Проблема: Ошибка аутентификации GitHub

**Решение:**

- Проверьте правильность токена
- Убедитесь, что токен имеет права `repo`
- Проверьте срок действия токена

### Проблема: Не удается расшифровать бэкап

**Решение:**

- Убедитесь, что используете тот же ключ шифрования
- Проверьте, что файл не поврежден

### Проблема: Нет места для бэкапов

**Решение:**

```bash
# Очистите старые бэкапы
docker-compose exec backup find /app/backups -name "*.sql.gz*" -mtime +30 -delete

# Или увеличьте KEEP_DAYS в backup_db.sh
```

---

## 📝 Примечания

- Бэкапы сохраняются в формате `siteheater_backup_YYYYMMDD_HHMMSS.sql.gz`
- Шифрованные бэкапы имеют расширение `.sql.gz.enc`
- По умолчанию хранятся бэкапы за последние 7 дней
- Размер бэкапа зависит от объема данных (обычно 1-10 MB в сжатом виде)

---

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте логи: `docker-compose logs backup`
2. Проверьте переменные окружения в `.env`
3. Убедитесь, что репозиторий приватный
4. Проверьте права доступа к токену

---

**Версия:** 1.0.0  
**Дата обновления:** 2025-01-12
