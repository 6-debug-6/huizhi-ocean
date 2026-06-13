"""
案例上传 API

端点：
    POST  /api/v1/cases/       — 用户提交检修案例（进入审核队列）
    GET   /api/v1/cases/       — 用户查看自己提交的案例列表
    GET   /api/v1/cases/{id}   — 案例详情
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.knowledge import CaseUpload, ReviewStatus

router = APIRouter()


class CaseCreateRequest:
    """用 pydantic 验证的请求体，在路由中通过 FastAPI 的 Body 依赖解析"""
    pass


from pydantic import BaseModel
from typing import Optional


class CaseCreate(BaseModel):
    title: str
    content: str
    device_models: list[str] = []
    fault_tags: list[str] = []
    is_experience_based: bool = False
    images: list[str] = []
    attachments: list[str] = []


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_case(
    req: CaseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    用户提交检修案例

    案例进入审核队列（review_status=pending_initial），
    管理员在审核队列中看到并审核。
    审核通过后自动转化为知识条目并入库。
    """
    case = CaseUpload(
        title=req.title,
        content=req.content,
        device_models=req.device_models or [],
        fault_tags=req.fault_tags or [],
        is_experience_based=req.is_experience_based,
        images=req.images or [],
        attachments=req.attachments or [],
        uploader_id=user.id,
    )
    db.add(case)
    await db.flush()

    # 审计日志（必须在 commit 前写入，和 case 在同一个事务中）
    from app.services.audit_service import log_audit
    await log_audit(db, user.id, "case.upload", "case_upload", case.id, f"提交案例：{req.title}")

    await db.commit()
    await db.refresh(case)

    return {
        "id": case.id,
        "message": "案例已提交，等待管理员审核",
        "review_status": case.review_status.value,
    }


@router.get("/")
async def list_my_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    查看我提交的案例列表
    """
    count_result = await db.execute(
        select(func.count(CaseUpload.id)).where(CaseUpload.uploader_id == user.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(CaseUpload)
        .where(CaseUpload.uploader_id == user.id)
        .order_by(CaseUpload.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    cases = result.scalars().all()

    items = []
    for c in cases:
        items.append({
            "id": c.id,
            "title": c.title,
            "device_models": c.device_models,
            "fault_tags": c.fault_tags,
            "is_experience_based": c.is_experience_based,
            "review_status": c.review_status.value,
            "reject_reason": c.reject_reason,
            "created_at": str(c.created_at) if c.created_at else "",
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{case_id}")
async def get_case_detail(
    case_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看案例详情"""
    result = await db.execute(select(CaseUpload).where(CaseUpload.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="案例不存在")
    if case.uploader_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看此案例")

    return {
        "id": case.id,
        "title": case.title,
        "content": case.content,
        "device_models": case.device_models,
        "fault_tags": case.fault_tags,
        "is_experience_based": case.is_experience_based,
        "images": case.images,
        "attachments": case.attachments,
        "review_status": case.review_status.value,
        "reject_reason": case.reject_reason,
        "review_comment": case.review_comment,
        "created_at": str(case.created_at) if case.created_at else "",
    }
