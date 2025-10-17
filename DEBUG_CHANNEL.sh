#!/bin/bash

# Скрипт для диагностики проблем с техническим каналом

echo "🔍 Диагностика технического канала"
echo "===================================="
echo ""

# 1. Проверка переменных окружения
echo "1️⃣ Проверка .env файла:"
if [ -f .env ]; then
    echo "✅ Файл .env найден"
    echo ""
    echo "Содержимое (уведомления):"
    grep -E "TECHNICAL_CHANNEL_ID|SEND_WARMING_NOTIFICATIONS" .env || echo "⚠️ Переменные не найдены в .env"
else
    echo "❌ Файл .env не найден!"
fi

echo ""
echo "2️⃣ Проверка загрузки в контейнере:"
docker-compose exec -T app python -c "
from app.config import config
print(f'TECHNICAL_CHANNEL_ID: {config.TECHNICAL_CHANNEL_ID}')
print(f'SEND_WARMING_NOTIFICATIONS: {config.SEND_WARMING_NOTIFICATIONS}')
print(f'Тип TECHNICAL_CHANNEL_ID: {type(config.TECHNICAL_CHANNEL_ID)}')
if config.TECHNICAL_CHANNEL_ID:
    print('✅ ID канала загружен')
else:
    print('❌ ID канала НЕ загружен')
" 2>/dev/null || echo "❌ Не удалось проверить конфигурацию"

echo ""
echo "3️⃣ Проверка логов при старте:"
docker-compose logs app | grep -E "Warming notifications|Technical channel" | tail -5

echo ""
echo "4️⃣ Тест отправки сообщения в канал:"
docker-compose exec -T app python -c "
import asyncio
from aiogram import Bot
from app.config import config

async def test():
    if not config.TECHNICAL_CHANNEL_ID:
        print('❌ TECHNICAL_CHANNEL_ID не загружен!')
        return
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    try:
        print(f'📤 Отправка тестового сообщения в канал: {config.TECHNICAL_CHANNEL_ID}')
        await bot.send_message(
            chat_id=config.TECHNICAL_CHANNEL_ID,
            text='🧪 <b>Тест подключения</b>\n\nЕсли вы видите это сообщение, канал настроен правильно!',
            parse_mode='HTML'
        )
        print('✅ Сообщение отправлено успешно!')
        print('Проверьте ваш канал.')
    except Exception as e:
        print(f'❌ Ошибка: {type(e).__name__}: {e}')
        print('')
        if 'not found' in str(e).lower() or 'chat not found' in str(e).lower():
            print('Причина: Неправильный ID канала')
            print('Решение: Получите ID канала заново через @userinfobot')
        elif 'forbidden' in str(e).lower():
            print('Причина: Бот не имеет доступа к каналу')
            print('Решение:')
            print('  1. Добавьте бота в канал как администратора')
            print('  2. Дайте права \"Публиковать сообщения\"')
        else:
            print(f'Неизвестная ошибка. Полное описание: {e}')
    finally:
        await bot.session.close()

asyncio.run(test())
" 2>/dev/null || echo "❌ Не удалось выполнить тест"

echo ""
echo "===================================="
echo "📋 Итог диагностики завершен"
echo ""
echo "Если тест не прошел, проверьте:"
echo "1. Бот добавлен в канал как администратор"
echo "2. У бота есть право 'Публиковать сообщения'"
echo "3. ID канала указан правильно (получен через @userinfobot)"
echo "4. После изменения .env выполнено: docker-compose restart app"

