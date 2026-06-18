"""
数据库连接管理

职责：
- 创建 SQLAlchemy 异步引擎和会话工厂
- 提供异步会话的依赖注入函数 (get_db)
- 提供开发阶段的自动建表函数 (init_db)
- 启动时清理残留 journal 文件，防止 SQLite 锁死
- 确保数据目录在启动时已存在
"""
import os
import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ========== 启动时确保数据目录存在 ==========
Path("data").mkdir(exist_ok=True)
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

# ========== 解析数据库文件路径（供清理和诊断使用） ==========
def _resolve_db_path() -> str:
    """从 DATABASE_URL 提取实际文件路径（经 normpath 规范化）"""
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite+aiosqlite:///"):
        p = db_url[len("sqlite+aiosqlite:///"):]
        if not os.path.isabs(p):
            p = os.path.join(os.getcwd(), p)
        return os.path.normpath(p)
    return ""

# ========== 清理残留 journal 文件 ==========
# SQLite 崩溃后残留的 -journal 文件会导致引擎连接时阻塞（恢复期间写锁不释放）。
# 仅在回滚日志模式下出现（WAL 模式没有此问题），安全删除。
def _cleanup_stale_journal():
    db_path = _resolve_db_path()
    if not db_path:
        return
    journal_path = db_path + "-journal"
    if os.path.exists(journal_path):
        try:
            os.remove(journal_path)
            logger.warning("已清理残留 journal 文件: %s", journal_path)
        except OSError:
            pass

_cleanup_stale_journal()

# ========== 创建异步数据库引擎 ==========
# timeout=10: 连接池满或 SQLite 锁定时最多等 10 秒（不会无限挂起）
# pool_pre_ping: 连接前检查有效性
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"timeout": 10},
    pool_pre_ping=True,
)

# 异步会话工厂
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型继承自此基类"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：为每个请求提供独立的数据库会话

    用法：
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    开发阶段自动建表函数

    启动时按顺序执行：
    1. 验证数据库文件可访问（不可访问时抛出明确错误而非静默挂起）
    2. 开启 WAL 模式（持久生效，首次执行后后续启动跳过）
    3. 注册 ORM 模型并建表
    4. 简易迁移（添加缺失列）
    """
    db_path = _resolve_db_path()
    if db_path:
        if not os.path.exists(db_path):
            # 数据库文件尚未创建，WAL 模式将在首次连接时设置
            pass
        elif not os.access(db_path, os.R_OK | os.W_OK):
            raise RuntimeError(f"数据库文件不可读写: {db_path}")
        logger.info("数据库路径: %s (存在=%s)", db_path, os.path.exists(db_path))

    async with engine.begin() as conn:
        # 启用 WAL 模式 + 优化同步策略（首次执行后持久生效）
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))

        from app.models import user, knowledge, conversation, ticket, audit  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

        # ========== 简易数据库迁移（开发阶段用） ==========
        try:
            await conn.run_sync(
                lambda sync_conn: sync_conn.execute(
                    text("ALTER TABLE knowledge_entries ADD COLUMN view_count INTEGER DEFAULT 0")
                )
            )
        except Exception:
            pass  # 列已存在则跳过
