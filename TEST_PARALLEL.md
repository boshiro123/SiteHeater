# 🧪 Тестирование параллельности chunks

## Как проверить, что chunks запускаются параллельно

### Ожидаемое поведение

Если chunks запускаются **параллельно**, в логах вы увидите:

```
🔥 Starting warming 1600 URLs with 2 repeat(s) (chunk size: 400)
📦 Split into 4 chunks for parallel warming
🚀 Launching 4 chunks in PARALLEL...
📦 Chunk 1/4: START warming 400 URLs (2 repeats)
📦 Chunk 2/4: START warming 400 URLs (2 repeats)
📦 Chunk 3/4: START warming 400 URLs (2 repeats)
📦 Chunk 4/4: START warming 400 URLs (2 repeats)
⏳ Waiting for all 4 chunks to complete...
📦 Chunk 1/4: repeat 1/2
📦 Chunk 2/4: repeat 1/2
📦 Chunk 3/4: repeat 1/2
📦 Chunk 4/4: repeat 1/2
✅ Warmed https://... (URL из chunk 1)
✅ Warmed https://... (URL из chunk 2)
✅ Warmed https://... (URL из chunk 3)
✅ Warmed https://... (URL из chunk 4)
... (вперемешку URL из всех chunks)
📦 Chunk 1/4: repeat 2/2
📦 Chunk 2/4: repeat 2/2
...
✅ Chunk 1/4 COMPLETED in 123.4s
✅ Chunk 3/4 COMPLETED in 125.1s
✅ Chunk 2/4 COMPLETED in 126.7s
✅ Chunk 4/4 COMPLETED in 127.2s
🎉 All 4 chunks finished!
✨ Warming completed
```

**Ключевые признаки параллельности:**

1. Все "START" появляются практически одновременно
2. URL из разных chunks идут вперемешку
3. Chunks завершаются примерно в одно время (±несколько секунд)

---

### Если chunks НЕ параллельны

Вы увидите последовательное выполнение:

```
📦 Chunk 1/4: START warming 400 URLs
✅ Warmed https://... (только chunk 1)
✅ Warmed https://... (только chunk 1)
...
✅ Chunk 1/4 COMPLETED
📦 Chunk 2/4: START warming 400 URLs  ← Начался ПОСЛЕ завершения chunk 1
✅ Warmed https://... (только chunk 2)
...
```

---

## Код, обеспечивающий параллельность

### В `warmer.py`:

```python
# ✅ ПРАВИЛЬНО - Параллельный запуск
chunk_tasks = [
    self.warm_chunk(chunk, client, semaphore, i + 1, total_chunks)
    for i, chunk in enumerate(chunks)
]
chunks_results = await asyncio.gather(*chunk_tasks)
```

`asyncio.gather()` запускает все задачи параллельно и ждет их завершения.

### ❌ НЕПРАВИЛЬНО - Последовательный запуск

```python
# Так делать НЕ НАДО
for i, chunk in enumerate(chunks):
    results = await self.warm_chunk(chunk, ...)  # Ждет завершения каждого
```

---

## Проверка производительности

### Тест на большом домене

Возьмем домен с 1600 URL, chunk_size=400 (4 chunks):

**Последовательно:**

- Chunk 1: 10 минут
- Chunk 2: 10 минут
- Chunk 3: 10 минут
- Chunk 4: 10 минут
- **Итого: 40 минут**

**Параллельно:**

- Все 4 chunks одновременно: 10 минут каждый
- **Итого: ~10-12 минут** (немного дольше из-за concurrency limit)

Если ваш прогрев занимает ~10-12 минут вместо 40, значит chunks работают параллельно! ✅

---

## Ограничения параллельности

### Semaphore (Concurrency)

Chunks запускаются параллельно, но внутри каждого chunk работает **общий** `semaphore`:

```python
semaphore = asyncio.Semaphore(self.concurrency)  # Например, 5
```

Это означает:

- Все chunks делят между собой лимит в 5 одновременных запросов
- Если у вас 4 chunks × 5 concurrency = теоретически 20 запросов
- Но из-за общего semaphore будет всего 5 одновременных запросов

### Почему так сделано?

1. **Защита целевого сервера** - не перегружаем сайт слишком большим количеством запросов
2. **Контролируемая нагрузка** - `WARMER_CONCURRENCY` контролирует общую нагрузку

### Можно ли увеличить реальную параллельность?

Да! Увеличьте `WARMER_CONCURRENCY`:

```env
# Было
WARMER_CONCURRENCY=5

# Стало (для 4 chunks)
WARMER_CONCURRENCY=20  # 5 запросов на chunk
```

**Внимание:** Убедитесь, что ваш сервер и целевой сайт справятся с нагрузкой!

---

## Диагностика проблем

### Симптом: Chunks запускаются последовательно

**Возможные причины:**

1. **Проблема в коде** - используется `await` в цикле вместо `gather()`
2. **Один event loop** - блокировка где-то в коде

**Решение:** Проверьте, что используется `asyncio.gather(*tasks)`

### Симптом: Chunks параллельны, но медленно

**Возможные причины:**

1. **Низкий WARMER_CONCURRENCY** - увеличьте значение
2. **Медленный целевой сайт** - сервер не справляется
3. **Сетевые задержки** - проблемы с интернетом

**Решение:**

```env
WARMER_CONCURRENCY=10  # или больше
WARMER_MIN_DELAY=0.3   # уменьшите задержку
WARMER_MAX_DELAY=1.0
```

### Симптом: URL идут не вперемешку из chunks

**Это нормально!**

Из-за `semaphore` запросы могут быть сериализованы, но chunks все равно работают параллельно на уровне задач.

Важно смотреть на:

- Время START всех chunks (должно быть одновременно)
- Время COMPLETED всех chunks (должно быть примерно одинаковое)

---

## Визуализация

### Параллельные chunks:

```
Time  Chunk 1  Chunk 2  Chunk 3  Chunk 4
0s    START    START    START    START
      ████     ████     ████     ████
5s    ████     ████     ████     ████
      ████     ████     ████     ████
10s   DONE     DONE     DONE     DONE
```

### Последовательные chunks:

```
Time  Chunk 1  Chunk 2  Chunk 3  Chunk 4
0s    START
      ████
5s    ████
      DONE
10s            START
               ████
15s            DONE
20s                     START
                        ████
25s                     DONE
30s                              START
                                 ████
35s                              DONE
```

---

## Команды для мониторинга

```bash
# Логи в реальном времени
docker-compose logs -f app | grep -E "Chunk|START|COMPLETED"

# Смотрим только chunks
docker-compose logs app | grep "📦"

# Время выполнения chunks
docker-compose logs app | grep "COMPLETED"
```

---

**Вывод:** Если вы видите все "START" chunks почти одновременно и "COMPLETED" примерно в одно время, значит chunks работают параллельно! ✅
