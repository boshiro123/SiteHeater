-- Добавление столбцов для групп URL

-- 1. Добавляем столбец url_group в domains
ALTER TABLE domains 
ADD COLUMN IF NOT EXISTS url_group INTEGER DEFAULT 3 NOT NULL;

-- 2. Добавляем столбец active_url_group в jobs
ALTER TABLE jobs 
ADD COLUMN IF NOT EXISTS active_url_group INTEGER DEFAULT 3 NOT NULL;

-- 3. Обновляем существующие записи (если нужно)
UPDATE domains SET url_group = 3 WHERE url_group IS NULL;
UPDATE jobs SET active_url_group = 3 WHERE active_url_group IS NULL;
