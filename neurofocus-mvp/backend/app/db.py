"""
Configuration de la base de données SQLAlchemy async.
Supporte PostgreSQL (asyncpg) et SQLite (aiosqlite) pour le dev.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from .config import settings


# Création du moteur asynchrone
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Fabrique de sessions
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles ORM."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dépendance FastAPI pour obtenir une session DB.
    Gestion automatique du rollback en cas d'erreur.
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialise les tables de la base de données."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
