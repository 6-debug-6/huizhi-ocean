"""
大模型配置 API

端点：
    GET    /api/v1/models/configs            — 列出所有模型配置（API Key 脱敏）
    POST   /api/v1/models/configs            — 新增配置
    PUT    /api/v1/models/configs/{id}        — 编辑配置
    POST   /api/v1/models/configs/{id}/activate — 激活配置（同类型其他自动停用）
    POST   /api/v1/models/configs/{id}/test   — 连通性测试
    DELETE /api/v1/models/configs/{id}        — 删除配置

权限：所有端点需 require_admin 依赖
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.config import get_settings
from app.models.user import User
from app.models.audit import ModelConfig
from app.services.audit_service import log_audit

settings = get_settings()
router = APIRouter()


@router.get("/configs")
async def list_configs(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出所有模型配置，API Key 仅显示后4位"""
    result = await db.execute(select(ModelConfig).order_by(ModelConfig.updated_at.desc()))
    configs = result.scalars().all()
    return [{
        "id": c.id,
        "model_name": c.model_name,
        "model_type": c.model_type,
        "api_base": c.api_base or "",
        "api_key_masked": ("****" + c.api_key[-4:]) if c.api_key and len(c.api_key) > 4 else "****",
        "is_active": c.is_active,
        "parameters": c.parameters or {},
        "updated_by": c.updated_by,
        "updated_at": str(c.updated_at) if c.updated_at else "",
    } for c in configs]


@router.post("/configs", status_code=status.HTTP_201_CREATED)
async def create_config(
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """新增模型配置"""
    config = ModelConfig(
        model_name=req.get("model_name", ""),
        model_type=req.get("model_type", "cloud"),
        api_base=req.get("api_base", ""),
        api_key=req.get("api_key", ""),
        parameters=req.get("parameters", {}),
        is_active=False,
        updated_by=admin.id,
    )
    db.add(config)
    await db.flush()
    await log_audit(db, admin.id, "model_config.create", "model_config", config.id, f"新增模型配置：{config.model_name}")
    await db.commit()
    await db.refresh(config)
    return {"id": config.id, "message": "配置已创建"}


@router.put("/configs/{config_id}")
async def update_config(
    config_id: int,
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """编辑模型配置"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    for field in ("model_name", "model_type", "api_base", "api_key", "parameters"):
        if field in req:
            setattr(config, field, req[field])
    config.updated_by = admin.id
    await log_audit(db, admin.id, "model_config.update", "model_config", config_id, f"更新模型配置：{config.model_name}")
    await db.commit()
    return {"message": "配置已更新"}


@router.post("/configs/{config_id}/activate")
async def activate_config(
    config_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """激活指定配置（同类型其他配置自动停用）"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")

    # 停用同类型其他配置
    await db.execute(
        update(ModelConfig)
        .where(ModelConfig.model_type == config.model_type)
        .values(is_active=False)
    )
    config.is_active = True
    config.updated_by = admin.id

    # 刷新 ModelRouter 缓存
    try:
        from app.services.llm_adapter import model_router
        model_router._config_cache_time = 0  # 使缓存失效
    except Exception:
        pass

    await log_audit(db, admin.id, "model_config.activate", "model_config", config_id, f"激活模型：{config.model_name}")
    await db.commit()
    return {"message": f"已激活 {config.model_name}"}


@router.post("/configs/{config_id}/test")
async def test_config(
    config_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """连通性测试：发送一条简单消息验证模型是否可用"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    if not config.api_key:
        return {"status": "error", "message": "未配置 API Key"}

    try:
        # 使用 httpx 发送简单测试请求
        import httpx
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        # 根据模型类型使用不同的API格式
        if "deepseek" in config.model_name.lower():
            body = {
                "model": config.model_name,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
            }
        else:
            body = {
                "model": config.model_name,
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 10,
            }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{config.api_base}/v1/chat/completions", headers=headers, json=body)
        if resp.status_code == 200:
            return {"status": "ok", "message": "连接成功"}
        else:
            return {"status": "error", "message": f"API 返回错误：{resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"连接失败：{str(e)}"}


@router.delete("/configs/{config_id}")
@router.post("/configs/{config_id}/delete")
async def delete_config(
    config_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除模型配置"""
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="配置不存在")
    if config.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除已激活的配置，请先激活其他配置")
    await db.delete(config)
    await db.commit()
    return {"message": "配置已删除"}
