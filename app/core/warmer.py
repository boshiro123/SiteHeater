"""
Модуль прогрева сайтов
"""
import asyncio
import logging
import random
from typing import List, Dict, Any
from datetime import datetime

import httpx
from app.config import config

logger = logging.getLogger(__name__)


class SiteWarmer:
    """Класс для прогрева сайтов"""
    
    def __init__(
        self,
        concurrency: int = None,
        min_delay: float = None,
        max_delay: float = None,
        repeat_count: int = None,
        timeout: int = None,
    ):
        self.concurrency = concurrency or config.WARMER_CONCURRENCY
        self.min_delay = min_delay or config.WARMER_MIN_DELAY
        self.max_delay = max_delay or config.WARMER_MAX_DELAY
        self.repeat_count = repeat_count or config.WARMER_REPEAT_COUNT
        self.timeout = timeout or config.WARMER_REQUEST_TIMEOUT
    
    async def warm_url(self, url: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Прогрев одного URL"""
        async with semaphore:
            start_time = datetime.utcnow()
            
            try:
                response = await client.get(
                    url,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(
                    f"✅ Warmed {url} | Status: {response.status_code} | Time: {elapsed:.2f}s"
                )
                
                return {
                    "url": url,
                    "status": "success",
                    "status_code": response.status_code,
                    "elapsed": elapsed,
                }
                
            except httpx.TimeoutException:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.warning(f"⏱ Timeout for {url} after {elapsed:.2f}s")
                
                return {
                    "url": url,
                    "status": "timeout",
                    "elapsed": elapsed,
                }
                
            except Exception as e:
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                logger.error(f"❌ Error warming {url}: {str(e)}")
                
                return {
                    "url": url,
                    "status": "error",
                    "error": str(e),
                    "elapsed": elapsed,
                }
            
            finally:
                # Случайная задержка между запросами
                delay = random.uniform(self.min_delay, self.max_delay)
                await asyncio.sleep(delay)
    
    async def warm_chunk(
        self,
        urls: List[str],
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        chunk_num: int,
        total_chunks: int
    ) -> List[Dict[str, Any]]:
        """Прогрев одного чанка URL"""
        start_time = datetime.utcnow()
        logger.info(f"📦 Chunk {chunk_num}/{total_chunks}: START warming {len(urls)} URLs ({self.repeat_count} repeats)")
        
        chunk_results = []
        
        for repeat in range(self.repeat_count):
            logger.info(f"📦 Chunk {chunk_num}/{total_chunks}: repeat {repeat + 1}/{self.repeat_count}")
            tasks = [self.warm_url(url, client, semaphore) for url in urls]
            results = await asyncio.gather(*tasks)
            chunk_results.extend(results)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Chunk {chunk_num}/{total_chunks} COMPLETED in {elapsed:.1f}s")
        return chunk_results
    
    async def warm_site(self, urls: List[str]) -> Dict[str, Any]:
        """
        Прогрев всех URL сайта с автоматическим разбиением на части
        
        Если URL много (> WARMER_CHUNK_SIZE), разбивает их на части
        и прогревает параллельно для ускорения и предотвращения "остывания"
        первых страниц.
        """
        chunk_size = config.WARMER_CHUNK_SIZE
        total_urls = len(urls)
        
        logger.info(
            f"🔥 Starting warming {total_urls} URLs with {self.repeat_count} repeat(s) "
            f"(chunk size: {chunk_size})"
        )
        
        # Разбиваем на чанки
        chunks = [urls[i:i + chunk_size] for i in range(0, len(urls), chunk_size)]
        total_chunks = len(chunks)
        
        if total_chunks > 1:
            logger.info(f"📦 Split into {total_chunks} chunks for parallel warming")
        
        all_results = []
        
        # Создаем отдельный semaphore для этого прогрева
        semaphore = asyncio.Semaphore(self.concurrency)
        
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        ) as client:
            # Запускаем прогрев всех чанков параллельно
            logger.info(f"🚀 Launching {total_chunks} chunks in PARALLEL...")
            
            chunk_tasks = [
                self.warm_chunk(chunk, client, semaphore, i + 1, total_chunks)
                for i, chunk in enumerate(chunks)
            ]
            
            logger.info(f"⏳ Waiting for all {total_chunks} chunks to complete...")
            chunks_results = await asyncio.gather(*chunk_tasks)
            
            logger.info(f"🎉 All {total_chunks} chunks finished!")
            
            # Объединяем результаты всех чанков
            for chunk_results in chunks_results:
                all_results.extend(chunk_results)
        
        # Подсчет статистики
        success_count = sum(1 for r in all_results if r["status"] == "success")
        timeout_count = sum(1 for r in all_results if r["status"] == "timeout")
        error_count = sum(1 for r in all_results if r["status"] == "error")
        
        total_time = sum(r["elapsed"] for r in all_results)
        avg_time = total_time / len(all_results) if all_results else 0
        
        stats = {
            "total_requests": len(all_results),
            "success": success_count,
            "timeout": timeout_count,
            "error": error_count,
            "total_time": round(total_time, 2),
            "avg_time": round(avg_time, 2),
        }
        
        logger.info(
            f"✨ Warming completed | "
            f"Success: {success_count} | "
            f"Timeout: {timeout_count} | "
            f"Error: {error_count} | "
            f"Avg time: {avg_time:.2f}s"
        )
        
        return stats


# Глобальный экземпляр
warmer = SiteWarmer()

