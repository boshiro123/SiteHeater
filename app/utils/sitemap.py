"""
Утилиты для работы с sitemap и краулинга
"""
import logging
from typing import List, Set
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SitemapParser:
    """Парсер sitemap и краулер"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    async def get_urls_from_sitemap(self, domain: str) -> List[str]:
        """Получение URL из sitemap.xml"""
        urls = []
        
        # Нормализуем домен
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        
        sitemap_urls = [
            f"{domain}/sitemap.xml",
            f"{domain}/sitemap_index.xml",
            f"{domain}/sitemap1.xml",
        ]
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for sitemap_url in sitemap_urls:
                try:
                    logger.info(f"Trying to fetch sitemap: {sitemap_url}")
                    response = await client.get(sitemap_url, follow_redirects=True)
                    
                    if response.status_code == 200:
                        urls_from_sitemap = self._parse_sitemap_xml(response.text)
                        urls.extend(urls_from_sitemap)
                        logger.info(f"✅ Found {len(urls_from_sitemap)} URLs in {sitemap_url}")
                        break
                        
                except Exception as e:
                    logger.debug(f"Failed to fetch {sitemap_url}: {e}")
                    continue
        
        return urls
    
    def _parse_sitemap_xml(self, xml_content: str) -> List[str]:
        """Парсинг XML sitemap"""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Обрабатываем различные namespace
            namespaces = {
                'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            }
            
            # Пытаемся найти URL элементы
            for url_elem in root.findall('.//ns:url/ns:loc', namespaces):
                if url_elem.text:
                    urls.append(url_elem.text.strip())
            
            # Если не нашли с namespace, пробуем без него
            if not urls:
                for url_elem in root.findall('.//url/loc'):
                    if url_elem.text:
                        urls.append(url_elem.text.strip())
            
            # Проверяем sitemap index
            for sitemap_elem in root.findall('.//ns:sitemap/ns:loc', namespaces):
                if sitemap_elem.text:
                    logger.info(f"Found sitemap index: {sitemap_elem.text}")
            
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        
        return urls
    
    async def crawl_site(self, domain: str, max_depth: int = 2, max_pages: int = 50) -> List[str]:
        """Краулинг сайта"""
        # Нормализуем домен
        if not domain.startswith(('http://', 'https://')):
            domain = f"https://{domain}"
        
        visited: Set[str] = set()
        to_visit: List[tuple] = [(domain, 0)]  # (url, depth)
        urls: List[str] = []
        
        parsed_domain = urlparse(domain)
        base_domain = f"{parsed_domain.scheme}://{parsed_domain.netloc}"
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        ) as client:
            while to_visit and len(visited) < max_pages:
                current_url, depth = to_visit.pop(0)
                
                if current_url in visited or depth > max_depth:
                    continue
                
                try:
                    logger.info(f"Crawling: {current_url} (depth={depth})")
                    response = await client.get(current_url)
                    
                    if response.status_code == 200:
                        visited.add(current_url)
                        urls.append(current_url)
                        
                        # Парсим HTML только если не достигли максимальной глубины
                        if depth < max_depth:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            
                            # Ищем ссылки
                            for link in soup.find_all('a', href=True):
                                href = link['href']
                                
                                # Преобразуем относительные ссылки в абсолютные
                                absolute_url = urljoin(current_url, href)
                                
                                # Проверяем, что ссылка ведет на тот же домен
                                parsed_url = urlparse(absolute_url)
                                
                                if (
                                    parsed_url.netloc == parsed_domain.netloc
                                    and absolute_url not in visited
                                    and absolute_url not in [u for u, _ in to_visit]
                                ):
                                    to_visit.append((absolute_url, depth + 1))
                
                except Exception as e:
                    logger.debug(f"Error crawling {current_url}: {e}")
                    continue
        
        logger.info(f"✅ Crawled {len(urls)} pages from {domain}")
        return urls
    
    async def discover_urls(self, domain: str) -> List[str]:
        """Полное обнаружение URL (sitemap + краулинг)"""
        logger.info(f"🔍 Discovering URLs for {domain}")
        
        all_urls = set()
        
        # Сначала пробуем sitemap
        sitemap_urls = await self.get_urls_from_sitemap(domain)
        all_urls.update(sitemap_urls)
        
        # Если в sitemap мало URL, дополняем краулингом
        if len(sitemap_urls) < 10:
            logger.info("Sitemap has few URLs, starting crawler...")
            crawled_urls = await self.crawl_site(domain, max_depth=1, max_pages=30)
            all_urls.update(crawled_urls)
        
        result = sorted(list(all_urls))
        logger.info(f"✅ Discovered {len(result)} unique URLs")
        
        return result


# Глобальный экземпляр
sitemap_parser = SitemapParser()

