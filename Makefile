.PHONY: help build up down restart logs clean migrate shell backup restore

help: ## Показать это сообщение помощи
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образы
	docker-compose build

up: ## Запустить все сервисы
	docker-compose up -d
	@echo "✅ Сервисы запущены!"
	@echo "📱 Telegram бот: работает"
	@echo "🗄️  pgAdmin: http://localhost:5050"

down: ## Остановить все сервисы
	docker-compose down

restart: ## Перезапустить все сервисы
	docker-compose restart

logs: ## Показать логи приложения
	docker-compose logs -f app

logs-all: ## Показать логи всех сервисов
	docker-compose logs -f

clean: ## Удалить все контейнеры и volumes
	docker-compose down -v
	@echo "🗑️  Все данные удалены!"

shell: ## Открыть shell в контейнере приложения
	docker-compose exec app /bin/bash

db-shell: ## Открыть PostgreSQL shell
	docker-compose exec postgres psql -U siteheater -d siteheater

migrate-create: ## Создать новую миграцию
	docker-compose exec app alembic revision --autogenerate -m "$(name)"

migrate-up: ## Применить миграции
	docker-compose exec app alembic upgrade head

migrate-down: ## Откатить последнюю миграцию
	docker-compose exec app alembic downgrade -1

status: ## Показать статус сервисов
	docker-compose ps

# === Команды для бэкапа ===

backup: ## Создать бэкап базы данных
	@echo "🔄 Создание бэкапа базы данных..."
	docker-compose run --rm backup
	@echo "✅ Бэкап создан!"

backup-list: ## Показать список бэкапов
	@echo "📦 Локальные бэкапы:"
	@docker-compose run --rm backup ls -lh /app/backups/ || echo "Бэкапов пока нет"

backup-clean: ## Удалить старые бэкапы (>30 дней)
	@echo "🧹 Очистка старых бэкапов..."
	@docker-compose run --rm backup find /app/backups -name "*.sql.gz*" -mtime +30 -delete
	@echo "✅ Готово!"

restore: ## Восстановить из бэкапа (использование: make restore BACKUP=файл.sql.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "❌ Укажите файл бэкапа: make restore BACKUP=siteheater_backup_20250112_120000.sql.gz"; \
		exit 1; \
	fi
	@echo "⚠️  ВНИМАНИЕ! Это удалит текущую базу данных!"
	@echo "Файл бэкапа: $(BACKUP)"
	@read -p "Продолжить? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose stop app; \
		docker-compose run --rm -e BACKUP_FILE=/app/backups/$(BACKUP) backup /bin/bash /scripts/restore_db.sh /app/backups/$(BACKUP); \
		docker-compose start app; \
		echo "✅ База данных восстановлена!"; \
	else \
		echo "❌ Восстановление отменено"; \
	fi

