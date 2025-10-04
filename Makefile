.PHONY: help build up down restart logs clean migrate shell

help: ## Показать это сообщение помощи
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

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

