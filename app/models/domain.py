"""
Модели базы данных
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, BigInteger, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовая модель"""
    pass


class Domain(Base):
    """Модель домена"""
    __tablename__ = "domains"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Админ, который добавил домен
    client_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Клиент, которому принадлежит домен
    url_group: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # 1=главная, 2=основные, 3=все
    
    # Relationships
    urls: Mapped[List["URL"]] = relationship("URL", back_populates="domain", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="domain", cascade="all, delete-orphan")
    warming_history: Mapped[List["WarmingHistory"]] = relationship("WarmingHistory", back_populates="domain", cascade="all, delete-orphan")
    client: Mapped[Optional["User"]] = relationship("User", back_populates="client_domains", foreign_keys=[client_id])
    
    def __repr__(self) -> str:
        return f"<Domain(id={self.id}, name={self.name}, client_id={self.client_id})>"


class URL(Base):
    """Модель URL"""
    __tablename__ = "urls"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="urls")
    
    def __repr__(self) -> str:
        return f"<URL(id={self.id}, url={self.url})>"


class Job(Base):
    """Модель задачи прогрева"""
    __tablename__ = "jobs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # например: "5m", "1h", "30m"
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_url_group: Mapped[int] = mapped_column(Integer, default=3, nullable=False)  # Группа URL для автопрогрева
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="jobs")
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, domain_id={self.domain_id}, schedule={self.schedule}, active={self.active}, group={self.active_url_group})>"


class User(Base):
    """Модель пользователя бота"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id (BigInteger для больших ID)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="client", nullable=False, index=True)  # admin или client
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, onupdate=datetime.utcnow)
    
    # Relationship: домены, где пользователь является клиентом
    client_domains: Mapped[List["Domain"]] = relationship("Domain", back_populates="client", foreign_keys="Domain.client_id")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"


class WarmingHistory(Base):
    """Модель истории прогревов для статистики"""
    __tablename__ = "warming_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Временные метки
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Статистика запросов
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Время ответа (в секундах)
    avg_response_time: Mapped[float] = mapped_column(Float, nullable=False)
    min_response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Тип прогрева: "manual" (разовый) или "scheduled" (автоматический)
    warming_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    
    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="warming_history")
    
    def __repr__(self) -> str:
        return f"<WarmingHistory(id={self.id}, domain_id={self.domain_id}, avg_time={self.avg_response_time}s)>"

