"""
FastAPI 应用入口
- 创建应用实例
- 配置 CORS 跨域中间件（允许前端开发服务器访问）
- 挂载静态文件目录（上传文件的访问入口）
- 注册各模块 API 路由
- 提供健康检查端点供运维监控
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时完成所有耗时初始化：
    1. 数据库建表 + 简易迁移
    2. 向量库 Embedding 预热（避免首次请求阻塞）
    """
    from app.core.database import init_db
    await init_db()

    # 预加载模型配置（启动时一次性从DB读取，运行时零DB访问避免锁冲突）
    from app.services.llm_adapter import model_router
    model_router.load_configs_sync()

    # 预热向量库 Embedding（后台执行，不阻塞启动）
    import asyncio
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _warmup_vector_store)
    yield


def _warmup_vector_store():
    """在后台线程中预热向量库，避免首次请求时阻塞"""
    try:
        from app.services.vector_store import vector_store
        vector_store.get_or_create_collection("maintenance_knowledge")
    except Exception:
        pass


def create_app() -> FastAPI:
    """
    应用工厂函数：创建并配置 FastAPI 应用实例
    将创建逻辑封装在函数中，方便测试时创建独立实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/docs",
        lifespan=lifespan,
    )

    # ========== CORS 跨域中间件 ==========
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========== 静态文件服务 ==========
    import os
    uploads_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # ========== 注册 API 路由模块 ==========
    from app.api import auth, knowledge, files, search, chat, review, tickets, import_doc, cases, task_guide, device_config, model_config

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["知识库"])
    app.include_router(files.router, prefix="/api/v1", tags=["文件"])
    app.include_router(search.router, prefix="/api/v1", tags=["检索"])
    app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
    app.include_router(review.router, prefix="/api/v1/review", tags=["审核"])
    app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["客服工单"])
    app.include_router(import_doc.router, prefix="/api/v1/import", tags=["文档导入"])
    app.include_router(cases.router, prefix="/api/v1/cases", tags=["案例上传"])
    app.include_router(task_guide.router, prefix="/api/v1/tasks", tags=["作业指引"])
    app.include_router(device_config.router, prefix="/api/v1/config", tags=["设备配置"])
    app.include_router(model_config.router, prefix="/api/v1/models", tags=["模型配置"])

    # ========== 健康检查端点 ==========
    @app.get("/api/v1/health")
    async def health_check():
        from datetime import datetime
        return {"status": "ok", "version": settings.APP_VERSION, "server_time": datetime.now().strftime("%H:%M:%S")}

    return app


# 模块级应用实例，uvicorn 启动时的入口
app = create_app()

# 直接运行此文件时启动开发服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
