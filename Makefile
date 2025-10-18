.PHONY: help build up down restart logs clean migrate shell backup restore backup-auto backup-stop

COMPOSE := docker-compose -f docker-compose.secure.yml

help: ## Показать это сообщение помощи
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образы (безопасная версия)
	$(COMPOSE) build --no-cache app

up: ## Запустить все сервисы
	$(COMPOSE) up -d
	@echo "✅ Сервисы запущены!"
	@echo "📱 Telegram бот: работает"
	@echo "🔐 Безопасная конфигурация активна"

down: ## Остановить все сервисы
	$(COMPOSE) down

restart: ## Перезапустить все сервисы (пересборка кода)
	@echo "🔄 Пересборка и перезапуск..."
	$(COMPOSE) build app
	$(COMPOSE) up -d
	@echo "✅ Готово!"

restart-fast: ## Быстрый перезапуск (без пересборки)
	$(COMPOSE) restart app

logs: ## Показать логи приложения
	$(COMPOSE) logs -f app

logs-all: ## Показать логи всех сервисов
	$(COMPOSE) logs -f

clean: ## Удалить все контейнеры и volumes
	$(COMPOSE) down -v
	@echo "🗑️  Все данные удалены!"

shell: ## Открыть shell в контейнере приложения
	$(COMPOSE) exec -u appuser app /bin/sh

db-shell: ## Открыть PostgreSQL shell
	$(COMPOSE) exec postgres psql -U siteheater -d siteheater

migrate-create: ## Создать новую миграцию
	$(COMPOSE) exec -u appuser app alembic revision --autogenerate -m "$(name)"

migrate-up: ## Применить миграции
	$(COMPOSE) exec -u appuser app alembic upgrade head

migrate-down: ## Откатить последнюю миграцию
	$(COMPOSE) exec -u appuser app alembic downgrade -1

status: ## Показать статус сервисов
	$(COMPOSE) ps

# === Команды для бэкапа ===

backup: ## Создать бэкап базы данных
	@echo "🔄 Создание бэкапа базы данных..."
	$(COMPOSE) run --rm backup
	@echo "✅ Бэкап создан!"

backup-list: ## Показать список бэкапов с подробной информацией
	@$(COMPOSE) run --rm backup ls -lh /app/backups/

backup-clean: ## Удалить старые бэкапы (>30 дней)
	@echo "🧹 Очистка старых бэкапов..."
	@$(COMPOSE) run --rm backup find /app/backups -name "*.sql.gz*" -mtime +30 -delete
	@echo "✅ Готово!"

backup-auto: ## Настроить автоматический бэкап (через cron)
	@bash scripts/setup_cron_backup.sh

backup-stop: ## Остановить автоматический бэкап (удалить из cron)
	@bash scripts/remove_cron_backup.sh

restore: ## Восстановить из бэкапа (использование: make restore BACKUP=файл.sql.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Укажите файл бэкапа: make restore BACKUP=siteheater_backup_20250112_120000.sql.gz"; \
		exit 1; \
	fi
	@echo "⚠️  ВНИМАНИЕ! Это удалит текущую базу данных!"
	@echo "Файл бэкапа: $(BACKUP)"
	@read -p "Продолжить? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		$(COMPOSE) stop app; \
		$(COMPOSE) run --rm --entrypoint /bin/sh backup -c "apk add --no-cache openssl bash && bash /scripts/restore_db.sh /app/backups/$(BACKUP)"; \
		$(COMPOSE) start app; \
		echo "✅ База данных восстановлена!"; \
	else \
		echo "❌ Восстановление отменено"; \
	fi

restore-quick: ## Быстрое восстановление из бэкапа (интерактивно)
	@bash scripts/quick_restore.sh

restore-github: ## Восстановление из бэкапа на GitHub
	@bash scripts/restore_from_github.sh
