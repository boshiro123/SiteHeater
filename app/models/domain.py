"""
Модели базы данных
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
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
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Relationships
    urls: Mapped[List["URL"]] = relationship("URL", back_populates="domain", cascade="all, delete-orphan")
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="domain", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Domain(id={self.id}, name={self.name})>"


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_run: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    domain: Mapped["Domain"] = relationship("Domain", back_populates="jobs")
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, domain_id={self.domain_id}, schedule={self.schedule}, active={self.active})>"

