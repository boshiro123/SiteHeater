"""
Генерация графиков для статистики прогрева
"""
import io
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import matplotlib
matplotlib.use('Agg')  # Для серверного использования без GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure

from app.models.domain import WarmingHistory

logger = logging.getLogger(__name__)


class GraphGenerator:
    """Генератор графиков статистики"""
    
    def __init__(self):
        # Настройки для красивых графиков
        plt.style.use('seaborn-v0_8-darkgrid')
        
    def generate_response_time_graph(
        self,
        history: List[WarmingHistory],
        domain_name: str,
        period: str = "24h"
    ) -> Optional[io.BytesIO]:
        """
        Генерация графика времени ответа сайта
        
        Args:
            history: История прогревов
            domain_name: Имя домена
            period: Период ("24h", "7d", "30d")
        
        Returns:
            BytesIO с изображением графика или None при ошибке
        """
        try:
            if not history:
                logger.warning("No history data to generate graph")
                return None
            
            # Извлекаем данные
            timestamps = [h.started_at for h in history]
            avg_times = [h.avg_response_time for h in history]
            
            # Создаем фигуру
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Рисуем линию среднего времени ответа
            ax.plot(timestamps, avg_times, marker='o', linestyle='-', 
                   linewidth=2, markersize=6, color='#2E86AB', label='Среднее время')
            
            # Добавляем заливку под графиком
            ax.fill_between(timestamps, avg_times, alpha=0.3, color='#2E86AB')
            
            # Рисуем горизонтальную линию среднего значения
            mean_time = sum(avg_times) / len(avg_times)
            ax.axhline(y=mean_time, color='red', linestyle='--', 
                      linewidth=1, alpha=0.7, label=f'Среднее: {mean_time:.2f}s')
            
            # Настройки осей
            ax.set_xlabel('Время', fontsize=12, fontweight='bold')
            ax.set_ylabel('Время ответа (сек)', fontsize=12, fontweight='bold')
            ax.set_title(f'📊 Скорость ответа сайта {domain_name}', 
                        fontsize=14, fontweight='bold', pad=20)
            
            # Форматирование оси X (времени)
            if len(timestamps) > 20:
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
            plt.xticks(rotation=45, ha='right')
            
            # Сетка
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='upper left', fontsize=10)
            
            # Добавляем информацию о статистике
            info_text = (
                f"Измерений: {len(history)}\n"
                f"Мин: {min(avg_times):.2f}s\n"
                f"Макс: {max(avg_times):.2f}s\n"
                f"Средн: {mean_time:.2f}s"
            )
            ax.text(0.98, 0.98, info_text, transform=ax.transAxes,
                   fontsize=9, verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            # Автоматическая подгонка
            plt.tight_layout()
            
            # Сохраняем в BytesIO
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            
            # Закрываем фигуру для освобождения памяти
            plt.close(fig)
            
            logger.info(f"Generated response time graph for {domain_name}")
            return buf
            
        except Exception as e:
            logger.error(f"Error generating graph: {e}", exc_info=True)
            return None
    
    def generate_success_rate_graph(
        self,
        history: List[WarmingHistory],
        domain_name: str
    ) -> Optional[io.BytesIO]:
        """
        Генерация графика процента успешности запросов
        
        Args:
            history: История прогревов
            domain_name: Имя домена
        
        Returns:
            BytesIO с изображением графика или None при ошибке
        """
        try:
            if not history:
                return None
            
            # Извлекаем данные
            timestamps = [h.started_at for h in history]
            success_rates = [
                (h.successful_requests / h.total_requests * 100) if h.total_requests > 0 else 0
                for h in history
            ]
            
            # Создаем фигуру
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Рисуем линию успешности
            colors = ['green' if rate >= 90 else 'orange' if rate >= 70 else 'red' 
                     for rate in success_rates]
            
            ax.plot(timestamps, success_rates, marker='o', linestyle='-',
                   linewidth=2, markersize=6, color='#06A77D', label='Успешность')
            
            # Раскрашиваем точки по цветам
            ax.scatter(timestamps, success_rates, c=colors, s=50, zorder=5)
            
            # Добавляем заливку
            ax.fill_between(timestamps, success_rates, alpha=0.3, color='#06A77D')
            
            # Горизонтальные линии уровней
            ax.axhline(y=90, color='green', linestyle='--', linewidth=1, alpha=0.5, label='90% (отлично)')
            ax.axhline(y=70, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='70% (норма)')
            
            # Настройки осей
            ax.set_xlabel('Время', fontsize=12, fontweight='bold')
            ax.set_ylabel('Успешность (%)', fontsize=12, fontweight='bold')
            ax.set_title(f'✅ Успешность запросов для {domain_name}',
                        fontsize=14, fontweight='bold', pad=20)
            ax.set_ylim(0, 105)
            
            # Форматирование оси X
            if len(timestamps) > 20:
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
            plt.xticks(rotation=45, ha='right')
            
            # Сетка и легенда
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='lower left', fontsize=10)
            
            # Статистика
            avg_success = sum(success_rates) / len(success_rates)
            info_text = (
                f"Измерений: {len(history)}\n"
                f"Мин: {min(success_rates):.1f}%\n"
                f"Макс: {max(success_rates):.1f}%\n"
                f"Средн: {avg_success:.1f}%"
            )
            ax.text(0.98, 0.98, info_text, transform=ax.transAxes,
                   fontsize=9, verticalalignment='top', horizontalalignment='right',
                   bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
            
            plt.tight_layout()
            
            # Сохраняем
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            logger.info(f"Generated success rate graph for {domain_name}")
            return buf
            
        except Exception as e:
            logger.error(f"Error generating success rate graph: {e}", exc_info=True)
            return None
    
    def generate_combined_graph(
        self,
        history: List[WarmingHistory],
        domain_name: str
    ) -> Optional[io.BytesIO]:
        """
        Генерация комбинированного графика (время + успешность)
        
        Args:
            history: История прогревов
            domain_name: Имя домена
        
        Returns:
            BytesIO с изображением графика или None при ошибке
        """
        try:
            if not history:
                return None
            
            # Извлекаем данные
            timestamps = [h.started_at for h in history]
            avg_times = [h.avg_response_time for h in history]
            success_rates = [
                (h.successful_requests / h.total_requests * 100) if h.total_requests > 0 else 0
                for h in history
            ]
            
            # Создаем фигуру с двумя подграфиками
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # === График 1: Время ответа ===
            ax1.plot(timestamps, avg_times, marker='o', linestyle='-',
                    linewidth=2, markersize=5, color='#2E86AB', label='Среднее время')
            ax1.fill_between(timestamps, avg_times, alpha=0.3, color='#2E86AB')
            
            mean_time = sum(avg_times) / len(avg_times)
            ax1.axhline(y=mean_time, color='red', linestyle='--',
                       linewidth=1, alpha=0.7, label=f'Среднее: {mean_time:.2f}s')
            
            ax1.set_ylabel('Время ответа (сек)', fontsize=11, fontweight='bold')
            ax1.set_title(f'📊 Статистика прогрева для {domain_name}',
                         fontsize=14, fontweight='bold', pad=15)
            ax1.grid(True, alpha=0.3, linestyle='--')
            ax1.legend(loc='upper left', fontsize=9)
            
            # === График 2: Успешность ===
            colors = ['green' if rate >= 90 else 'orange' if rate >= 70 else 'red'
                     for rate in success_rates]
            
            ax2.plot(timestamps, success_rates, marker='o', linestyle='-',
                    linewidth=2, markersize=5, color='#06A77D', label='Успешность')
            ax2.scatter(timestamps, success_rates, c=colors, s=40, zorder=5)
            ax2.fill_between(timestamps, success_rates, alpha=0.3, color='#06A77D')
            
            ax2.axhline(y=90, color='green', linestyle='--', linewidth=1, alpha=0.5)
            ax2.axhline(y=70, color='orange', linestyle='--', linewidth=1, alpha=0.5)
            
            ax2.set_xlabel('Время', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Успешность (%)', fontsize=11, fontweight='bold')
            ax2.set_ylim(0, 105)
            ax2.grid(True, alpha=0.3, linestyle='--')
            ax2.legend(loc='lower left', fontsize=9)
            
            # Форматирование оси X для обоих графиков
            for ax in [ax1, ax2]:
                if len(timestamps) > 20:
                    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m %H:%M'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
            
            plt.tight_layout()
            
            # Сохраняем
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            logger.info(f"Generated combined graph for {domain_name}")
            return buf
            
        except Exception as e:
            logger.error(f"Error generating combined graph: {e}", exc_info=True)
            return None


# Глобальный экземпляр
graph_generator = GraphGenerator()

