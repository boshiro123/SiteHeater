"""
Работа с базой данных
"""
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.config import config
from app.models.domain import Base, Domain, URL, Job, User

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер базы данных"""
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")
    
    async def close(self) -> None:
        """Закрытие соединения"""
        await self.engine.dispose()
        logger.info("Database connection closed")
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Получение сессии"""
        async with self.async_session() as session:
            yield session
    
    # Domain methods
    async def create_domain(
        self,
        name: str,
        user_id: int,
        urls: List[str]
    ) -> Domain:
        """Создание домена с URL"""
        async with self.async_session() as session:
            # Проверяем, есть ли уже такой домен
            result = await session.execute(
                select(Domain).where(Domain.name == name)
            )
            existing_domain = result.scalar_one_or_none()
            
            if existing_domain:
                # Обновляем существующий домен
                existing_domain.is_active = True
                existing_domain.user_id = user_id
                
                # Удаляем старые URL
                await session.execute(
                    delete(URL).where(URL.domain_id == existing_domain.id)
                )
                
                # Добавляем новые URL
                for url in urls:
                    url_obj = URL(domain_id=existing_domain.id, url=url)
                    session.add(url_obj)
                
                await session.commit()
                await session.refresh(existing_domain)
                return existing_domain
            
            # Создаем новый домен
            domain = Domain(name=name, user_id=user_id)
            session.add(domain)
            await session.flush()
            
            # Добавляем URL
            for url in urls:
                url_obj = URL(domain_id=domain.id, url=url)
                session.add(url_obj)
            
            await session.commit()
            await session.refresh(domain)
            return domain
    
    async def get_domain_by_name(self, name: str) -> Optional[Domain]:
        """Получение домена по имени"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Domain)
                .where(Domain.name == name)
                .options(selectinload(Domain.urls), selectinload(Domain.jobs))
            )
            return result.scalar_one_or_none()
    
    async def get_domain_by_id(self, domain_id: int) -> Optional[Domain]:
        """Получение домена по ID"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Domain)
                .where(Domain.id == domain_id)
                .options(selectinload(Domain.urls), selectinload(Domain.jobs))
            )
            return result.scalar_one_or_none()
    
    async def get_all_domains(self, user_id: Optional[int] = None) -> List[Domain]:
        """Получение всех доменов пользователя"""
        async with self.async_session() as session:
            query = select(Domain).options(selectinload(Domain.urls), selectinload(Domain.jobs))
            
            if user_id:
                query = query.where(Domain.user_id == user_id)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def delete_domain(self, domain_id: int) -> bool:
        """Удаление домена"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Domain).where(Domain.id == domain_id)
            )
            domain = result.scalar_one_or_none()
            
            if not domain:
                return False
            
            await session.delete(domain)
            await session.commit()
            return True
    
    # Job methods
    async def create_job(
        self,
        domain_id: int,
        schedule: Optional[str] = None,
        active: bool = True
    ) -> Job:
        """Создание задачи"""
        async with self.async_session() as session:
            # Деактивируем все старые задачи для этого домена
            await session.execute(
                select(Job)
                .where(Job.domain_id == domain_id)
            )
            result = await session.execute(
                select(Job).where(Job.domain_id == domain_id)
            )
            old_jobs = result.scalars().all()
            for old_job in old_jobs:
                old_job.active = False
            
            # Создаем новую задачу
            job = Job(domain_id=domain_id, schedule=schedule, active=active)
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job
    
    async def get_active_jobs(self) -> List[Job]:
        """Получение активных задач"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job)
                .where(Job.active == True)
                .options(selectinload(Job.domain).selectinload(Domain.urls))
            )
            return list(result.scalars().all())
    
    async def update_job_last_run(self, job_id: int) -> None:
        """Обновление времени последнего запуска"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job).where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if job:
                job.last_run = datetime.utcnow()
                await session.commit()
    
    async def deactivate_jobs_for_domain(self, domain_id: int) -> None:
        """Деактивация всех задач для домена"""
        async with self.async_session() as session:
            result = await session.execute(
                select(Job).where(Job.domain_id == domain_id)
            )
            jobs = result.scalars().all()
            
            for job in jobs:
                job.active = False
            
            await session.commit()
    
    # User methods
    async def register_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Регистрация или обновление пользователя"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user:
                # Обновляем информацию
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.last_activity = datetime.utcnow()
                user.is_active = True
            else:
                # Создаем нового пользователя
                user = User(
                    id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
            
            await session.commit()
            await session.refresh(user)
            return user
    
    async def get_all_active_users(self) -> List[User]:
        """Получение всех активных пользователей"""
        async with self.async_session() as session:
            result = await session.execute(
                select(User).where(User.is_active == True)
            )
            return list(result.scalars().all())


# Глобальный экземпляр
db_manager = DatabaseManager(config.DATABASE_URL)

