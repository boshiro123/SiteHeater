"""
Группировка URL по категориям для прогрева
"""
import logging
from typing import List, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class URLGrouper:
    """Группировщик URL для разных стратегий прогрева"""
    
    # Паттерны для группы 2 (основные страницы)
    GROUP_2_PATTERNS = [
        '/page/',
        '/blogs/',
        '/blog/',
        '/collection/',
        '/collections/',
        '/catalog/',
        '/category/',
        '/categories/',
    ]
    
    def __init__(self):
        pass
    
    def get_homepage_url(self, domain_name: str) -> str:
        """
        Получение URL главной страницы
        
        Args:
            domain_name: Имя домена (example.com)
        
        Returns:
            Полный URL главной страницы (https://example.com/ или http://example.com/)
        """
        # Проверяем есть ли протокол
        if not domain_name.startswith(('http://', 'https://')):
            # Пробуем https по умолчанию
            homepage = f"https://{domain_name}/"
        else:
            parsed = urlparse(domain_name)
            homepage = f"{parsed.scheme}://{parsed.netloc}/"
        
        return homepage
    
    def is_homepage(self, url: str, domain_name: str) -> bool:
        """
        Проверка, является ли URL главной страницей
        
        Args:
            url: Проверяемый URL
            domain_name: Имя домена
        
        Returns:
            True если это главная страница
        """
        parsed = urlparse(url)
        homepage = self.get_homepage_url(domain_name)
        parsed_home = urlparse(homepage)
        
        # Главная страница: домен + "/" или пустой path
        return (
            parsed.netloc == parsed_home.netloc and
            parsed.path in ['/', '']
        )
    
    def is_group_2_url(self, url: str) -> bool:
        """
        Проверка, относится ли URL к группе 2 (основные страницы)
        
        Args:
            url: Проверяемый URL
        
        Returns:
            True если URL содержит паттерны группы 2
        """
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.GROUP_2_PATTERNS)
    
    def group_urls(self, urls: List[str], domain_name: str) -> Dict[int, List[str]]:
        """
        Группировка URL по категориям
        
        Args:
            urls: Список всех URL домена
            domain_name: Имя домена
        
        Returns:
            Словарь {group_id: [urls]}
            - group 1: только главная страница
            - group 2: главная + основные страницы (/page, /blogs, /blog, /collection и т.д.)
            - group 3: все страницы
        """
        homepage = self.get_homepage_url(domain_name)
        
        # Группа 1: только главная
        group_1 = []
        
        # Группа 2: главная + основные
        group_2 = []
        
        # Группа 3: все
        group_3 = list(urls)
        
        # Сортировка URL
        for url in urls:
            if self.is_homepage(url, domain_name):
                group_1.append(url)
                group_2.append(url)
            elif self.is_group_2_url(url):
                group_2.append(url)
        
        # Если главной страницы нет в списке, добавляем её
        if not group_1:
            group_1.append(homepage)
            group_2.insert(0, homepage)
            if homepage not in group_3:
                group_3.insert(0, homepage)
        
        logger.info(
            f"URL grouping for {domain_name}: "
            f"Group 1 (homepage): {len(group_1)}, "
            f"Group 2 (main pages): {len(group_2)}, "
            f"Group 3 (all): {len(group_3)}"
        )
        
        return {
            1: group_1,
            2: group_2,
            3: group_3
        }
    
    def filter_urls_by_group(self, urls: List[str], domain_name: str, group: int) -> List[str]:
        """
        Фильтрация URL по группе
        
        Args:
            urls: Список всех URL
            domain_name: Имя домена
            group: Номер группы (1, 2 или 3)
        
        Returns:
            Отфильтрованный список URL для указанной группы
        """
        if group not in [1, 2, 3]:
            logger.warning(f"Invalid group {group}, defaulting to group 3")
            return urls
        
        grouped = self.group_urls(urls, domain_name)
        return grouped.get(group, urls)
    
    def get_group_description(self, group: int) -> str:
        """
        Получение описания группы
        
        Args:
            group: Номер группы
        
        Returns:
            Текстовое описание группы
        """
        descriptions = {
            1: "🏠 Только главная страница",
            2: "📄 Основные страницы (главная + /page, /blogs, /blog, /collection)",
            3: "🌐 Все страницы сайта"
        }
        return descriptions.get(group, "Неизвестная группа")
    
    def get_group_stats(self, urls: List[str], domain_name: str) -> Dict[int, int]:
        """
        Получение статистики по группам
        
        Args:
            urls: Список всех URL
            domain_name: Имя домена
        
        Returns:
            Словарь {group_id: count}
        """
        grouped = self.group_urls(urls, domain_name)
        return {
            1: len(grouped[1]),
            2: len(grouped[2]),
            3: len(grouped[3])
        }


# Глобальный экземпляр
url_grouper = URLGrouper()

