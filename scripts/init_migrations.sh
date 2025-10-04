#!/bin/bash

# Скрипт для инициализации миграций Alembic

echo "🔧 Initializing Alembic migrations..."

# Создаем начальную миграцию
alembic revision --autogenerate -m "Initial migration"

echo "✅ Migration created!"
echo "📝 To apply migrations, run: alembic upgrade head"

