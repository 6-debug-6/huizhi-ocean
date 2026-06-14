"""
设备配置 API

端点：
    GET    /api/v1/config/device-models      — 设备型号列表
    POST   /api/v1/config/device-models      — 新增设备型号（仅管理员）
    PUT    /api/v1/config/device-models/{id}  — 编辑设备型号（仅管理员）
    DELETE /api/v1/config/device-models/{id}  — 删除设备型号（仅管理员，有关联知识时拒绝）

    GET    /api/v1/config/fault-tags          — 故障标签列表（扁平）
    POST   /api/v1/config/fault-tags          — 新增故障标签（仅管理员）
    PUT    /api/v1/config/fault-tags/{id}      — 编辑故障标签（仅管理员）
    DELETE /api/v1/config/fault-tags/{id}      — 删除故障标签（仅管理员，有关联知识时拒绝）

权限：所有写操作需 require_admin 依赖
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.knowledge import KnowledgeEntry
from app.models.audit import DeviceModel, FaultCategory
from app.services.audit_service import log_audit

router = APIRouter()


# ========== 设备型号管理 ==========

@router.get("/device-models")
async def list_device_models(
    status_filter: str = Query("active", description="active / archived / all"),
    db: AsyncSession = Depends(get_db),
):
    """获取设备型号列表"""
    query = select(DeviceModel)
    if status_filter and status_filter != "all":
        query = query.where(DeviceModel.status == status_filter)
    query = query.order_by(DeviceModel.name)
    result = await db.execute(query)
    models = result.scalars().all()
    return [{
        "id": m.id,
        "name": m.name,
        "production_line": m.production_line or "",
        "category": m.category or "",
        "status": m.status or "active",
        "spec_data": m.spec_data or {},
    } for m in models]


@router.post("/device-models", status_code=status.HTTP_201_CREATED)
async def create_device_model(
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """新增设备型号"""
    existing = await db.execute(select(DeviceModel).where(DeviceModel.name == req.get("name", "")))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="设备型号已存在")
    model = DeviceModel(
        name=req.get("name", ""),
        production_line=req.get("production_line", ""),
        category=req.get("category", ""),
        spec_data=req.get("spec_data", {}),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return {"id": model.id, "message": "设备型号已创建"}


@router.put("/device-models/{model_id}")
async def update_device_model(
    model_id: int,
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """编辑设备型号"""
    result = await db.execute(select(DeviceModel).where(DeviceModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备型号不存在")
    for field in ("name", "production_line", "category", "status"):
        if field in req:
            setattr(model, field, req[field])
    if "spec_data" in req:
        model.spec_data = req["spec_data"]
    await db.commit()
    return {"message": "设备型号已更新"}


@router.delete("/device-models/{model_id}")
@router.post("/device-models/{model_id}/delete")
async def delete_device_model(
    model_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除设备型号（有关联知识条目时拒绝）"""
    result = await db.execute(select(DeviceModel).where(DeviceModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备型号不存在")
    # 检查是否有关联的知识条目
    entries = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.status != "archived"))
    for e in entries.scalars().all():
        if model.name in (e.device_models or []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"设备型号被知识条目「{e.title}」引用，无法删除，请先归档")
    await db.delete(model)
    await db.commit()
    return {"message": "设备型号已删除"}


# ========== 故障标签管理（扁平） ==========

@router.get("/fault-tags")
async def list_fault_tags(db: AsyncSession = Depends(get_db)):
    """获取扁平故障标签列表（含使用次数统计）"""
    result = await db.execute(select(FaultCategory).order_by(FaultCategory.name))
    categories = result.scalars().all()

    # 统计每个标签被多少知识条目使用
    tag_usage = {}
    entries = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.status != "archived"))
    for e in entries.scalars().all():
        for tag in (e.fault_tags or []):
            if tag:
                tag_usage[tag] = tag_usage.get(tag, 0) + 1

    return [{
        "id": c.id,
        "name": c.name,
        "usage_count": tag_usage.get(c.name, 0),
    } for c in categories]


@router.post("/fault-tags", status_code=status.HTTP_201_CREATED)
async def create_fault_tag(
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """新增故障标签"""
    name = req.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签名称不能为空")
    existing = await db.execute(select(FaultCategory).where(FaultCategory.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="标签已存在")
    tag = FaultCategory(name=name)
    db.add(tag)
    await log_audit(db, admin.id, "fault_tag.create", "fault_category", 0, f"新增故障标签：{name}")
    await db.commit()
    await db.refresh(tag)
    return {"id": tag.id, "name": tag.name, "message": "标签已创建"}


@router.put("/fault-tags/{tag_id}")
async def update_fault_tag(
    tag_id: int,
    req: dict,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """编辑故障标签名称"""
    result = await db.execute(select(FaultCategory).where(FaultCategory.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    old_name = tag.name
    new_name = req.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签名称不能为空")
    tag.name = new_name
    await log_audit(db, admin.id, "fault_tag.update", "fault_category", tag_id, f"故障标签：{old_name} → {new_name}")
    await db.commit()
    return {"message": "标签已更新"}


@router.delete("/fault-tags/{tag_id}")
@router.post("/fault-tags/{tag_id}/delete")
async def delete_fault_tag(
    tag_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除故障标签（有关联知识条目时拒绝）"""
    result = await db.execute(select(FaultCategory).where(FaultCategory.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    # 检查关联的知识条目
    entries = await db.execute(select(KnowledgeEntry).where(KnowledgeEntry.status != "archived"))
    for e in entries.scalars().all():
        if tag.name in (e.fault_tags or []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"标签被知识条目「{e.title}」引用，无法删除")
    await log_audit(db, admin.id, "fault_tag.delete", "fault_category", tag_id, f"删除故障标签：{tag.name}")
    await db.delete(tag)
    await db.commit()
    return {"message": "标签已删除"}
