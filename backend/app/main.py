"""
FastAPI 应用入口
- 创建应用实例
- 配置 CORS 跨域中间件（允许前端开发服务器访问）
- 挂载静态文件目录（上传文件的访问入口）
- 注册各模块 API 路由（认证、知识库、文件、检索、对话）
- 提供健康检查端点供运维监控
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import get_settings

# 全局配置单例，通过 lru_cache 缓存，避免重复读取 .env 文件
settings = get_settings()


def create_app() -> FastAPI:
    """
    应用工厂函数：创建并配置 FastAPI 应用实例
    将创建逻辑封装在函数中，方便测试时创建独立实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        # Swagger UI 文档地址：/docs
        docs_url="/docs",
    )

    # ========== CORS 跨域中间件 ==========
    # 允许前端开发服务器 (localhost:5173) 跨域访问后端 API
    # allow_methods=["*"] 允许所有 HTTP 方法
    # allow_headers=["*"] 允许所有请求头（包括 Authorization）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ========== 静态文件服务 ==========
    # 将上传文件目录挂载到 /uploads 路径
    # 用户上传的图片、附件等可通过 /uploads/images/xxx.png 直接访问
    import os
    uploads_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # ========== 注册 API 路由模块 ==========
    # 各路由模块独立管理各自的端点，通过 include_router 注册到主应用
    from app.api import auth, knowledge, files, search, chat, review, tickets, import_doc, cases, task_guide

    # 认证模块：注册/登录/获取当前用户/密码重置
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])

    # 知识库模块：知识条目的 CRUD、版本管理、归档
    app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["知识库"])

    # 文件模块：图片和文档的上传、格式转换
    app.include_router(files.router, prefix="/api/v1", tags=["文件"])

    # 检索模块：多模态搜索（文本+图片+设备型号），意图重写
    app.include_router(search.router, prefix="/api/v1", tags=["检索"])

    # 对话模块：AI 对话（RAG 链路）、会话管理、反馈收集
    app.include_router(chat.router, prefix="/api/v1", tags=["对话"])

    # 审核模块：案例审核队列、两级审核（初审+复审）、自动入库
    app.include_router(review.router, prefix="/api/v1/review", tags=["审核"])

    # 客服工单模块：工单提交/回复/状态流转/转知识条目
    app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["客服工单"])

    # 文档导入模块：PDF 上传解析 → 知识片段 → 向量化入库
    app.include_router(import_doc.router, prefix="/api/v1/import", tags=["文档导入"])

    # 案例上传模块：用户提交检修案例，进入审核队列
    app.include_router(cases.router, prefix="/api/v1/cases", tags=["案例上传"])

    # 作业指引模块：流程模板管理 + 任务创建/步骤确认/暂停/交接
    app.include_router(task_guide.router, prefix="/api/v1/tasks", tags=["作业指引"])

    # ========== 健康检查端点 ==========
    # 供部署环境的负载均衡器或监控系统探测服务是否存活
    @app.get("/api/v1/health")
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    return app


# 模块级应用实例，uvicorn 启动时的入口
app = create_app()

# 直接运行此文件时启动开发服务器
if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" 允许局域网内其他设备访问
    # reload=True 代码变更后自动重启（仅开发阶段使用）
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
