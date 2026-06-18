"""
数据库连接管理

职责：
- 创建 SQLAlchemy 异步引擎和会话工厂
- 提供异步会话的依赖注入函数 (get_db)
- 提供开发阶段的自动建表函数 (init_db)
- 确保数据目录在启动时已存在
"""
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

# ========== 启动时确保数据目录存在 ==========
Path("data").mkdir(exist_ok=True)
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

# ========== 创建异步数据库引擎 ==========
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

# 异步会话工厂
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型继承自此基类"""
    pass


async def get_db() -> AsyncSession:
    """
    FastAPI 依赖注入：为每个请求提供独立的数据库会话
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    开发阶段自动建表函数
    导入所有模型模块以注册到 Base.metadata，然后执行 CREATE TABLE
    同时执行简易迁移（添加缺失的列）
    """
    async with engine.begin() as conn:
        from app.models import user, knowledge, conversation, ticket, audit  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

        # ========== 简易数据库迁移（开发阶段用） ==========
        # 对已存在的表添加新列时，若列已存在则忽略错误
        try:
            await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    "ALTER TABLE knowledge_entries ADD COLUMN view_count INTEGER DEFAULT 0"
                )
            )
        except Exception:
            pass  # 列已存在则跳过
