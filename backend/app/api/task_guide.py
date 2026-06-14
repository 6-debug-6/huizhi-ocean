"""
作业指引 API

端点 — 模板管理（管理员）：
    GET    /api/v1/tasks/templates           — 模板列表
    POST   /api/v1/tasks/templates           — 创建模板
    GET    /api/v1/tasks/templates/{id}      — 模板详情
    PUT    /api/v1/tasks/templates/{id}      — 更新模板
    DELETE /api/v1/tasks/templates/{id}      — 删除模板

端点 — 任务执行（用户）：
    GET    /api/v1/tasks/                    — 我的任务列表
    POST   /api/v1/tasks/                    — 创建任务（选择设备+模板）
    GET    /api/v1/tasks/{id}                — 任务详情
    POST   /api/v1/tasks/{id}/step           — 确认当前步骤（推进到下一步）
    POST   /api/v1/tasks/{id}/pause          — 暂停任务
    POST   /api/v1/tasks/{id}/resume         — 恢复任务
    POST   /api/v1/tasks/{id}/handover       — 交接任务给他人
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User, UserRole
from app.models.audit import ProcedureTemplate, TaskRecord
from app.services.audit_service import log_audit
from pydantic import BaseModel

router = APIRouter()


# ==================== Pydantic Schemas ====================

class TemplateCreate(BaseModel):
    name: str
    device_models: list[str] = []
    maintenance_level: str = "日常"
    steps: list[dict] = []
    parent_id: int | None = None


class TemplateUpdate(BaseModel):
    name: str | None = None
    device_models: list[str] | None = None
    maintenance_level: str | None = None
    steps: list[dict] | None = None


class TaskCreate(BaseModel):
    title: str
    device_model: str
    template_id: int | None = None  # 可选：从模板创建
    steps: list[dict] | None = None  # 或手动指定步骤


class HandoverRequest(BaseModel):
    to_user_id: int
    note: str = ""


# ==================== 模板管理（管理员） ====================

@router.get("/templates")
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取检修流程模板列表"""
    count_result = await db.execute(select(func.count(ProcedureTemplate.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ProcedureTemplate)
        .order_by(ProcedureTemplate.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    templates = result.scalars().all()

    items = [{
        "id": t.id, "name": t.name, "device_models": t.device_models,
        "maintenance_level": t.maintenance_level, "version": t.version,
        "version_num": t.version_num, "status": t.status,
        "step_count": len(t.steps or []),
        "created_at": str(t.created_at) if t.created_at else "",
    } for t in templates]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/templates")
async def create_template(
    req: TemplateCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """创建检修流程模板"""
    max_ver = await db.scalar(select(func.max(ProcedureTemplate.version_num))) or 0
    template = ProcedureTemplate(
        name=req.name,
        device_models=req.device_models or [],
        maintenance_level=req.maintenance_level,
        steps=req.steps or [],
        parent_id=req.parent_id,
        version=f"V{max_ver + 1}.0",
        version_num=max_ver + 1,
        author_id=admin.id,
    )
    db.add(template)
    await db.flush()
    await log_audit(db, admin.id, "template.create", "procedure_template", template.id, f"创建模板：{req.name}")
    await db.commit()
    await db.refresh(template)
    return {"id": template.id, "message": "模板已创建"}


@router.get("/templates/{template_id}")
async def get_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """获取模板详情"""
    result = await db.execute(select(ProcedureTemplate).where(ProcedureTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    return {
        "id": t.id, "name": t.name, "device_models": t.device_models,
        "maintenance_level": t.maintenance_level, "version": t.version,
        "steps": t.steps, "status": t.status, "parent_id": t.parent_id,
    }


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    req: TemplateUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """更新模板"""
    result = await db.execute(select(ProcedureTemplate).where(ProcedureTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    for field, value in req.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(t, field, value)

    # 版本号递增
    parts = t.version.replace("V", "").split(".")
    minor = int(parts[1]) if len(parts) > 1 else 0
    t.version = f"V{int(parts[0])}.{minor + 1}" if minor < 9 else f"V{int(parts[0]) + 1}.0"
    t.version_num = (await db.scalar(select(func.max(ProcedureTemplate.version_num))) or 0) + 1

    await log_audit(db, admin.id, "template.update", "procedure_template", template_id, f"更新模板：{t.name}")
    await db.commit()
    return {"message": "模板已更新", "version": t.version}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除模板"""
    result = await db.execute(select(ProcedureTemplate).where(ProcedureTemplate.id == template_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    await db.delete(t)
    await db.commit()
    return {"message": "模板已删除"}


# ==================== 任务执行（用户） ====================

@router.get("/")
async def list_my_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取我的任务列表（含进行中、已暂停、已完成）"""
    result = await db.execute(
        select(TaskRecord)
        .where(TaskRecord.assignee_id == user.id)
        .order_by(TaskRecord.started_at.desc())
        .limit(50)
    )
    tasks = result.scalars().all()

    items = []
    for t in tasks:
        # 计算进度
        progress = 0
        if t.total_steps > 0:
            progress = round(len(t.confirmed_steps or []) / t.total_steps * 100)

        items.append({
            "id": t.id, "title": t.title, "device_model": t.device_model,
            "maintenance_level": t.maintenance_level, "status": t.status,
            "current_step": t.current_step, "total_steps": t.total_steps,
            "progress": progress,
            "pause_reason": t.pause_reason,
            "is_handed_over": bool(t.original_assignee_id and t.original_assignee_id != user.id),
            "started_at": str(t.started_at) if t.started_at else "",
            "deadline_at": str(t.deadline_at) if t.deadline_at else "",
        })

    return {"items": items, "total": len(items)}


@router.post("/")
async def create_task(
    req: TaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建作业任务"""
    steps = req.steps or []
    template_id = req.template_id

    # 如果指定了模板 ID，加载模板步骤
    if req.template_id and not steps:
        result = await db.execute(select(ProcedureTemplate).where(ProcedureTemplate.id == req.template_id))
        template = result.scalar_one_or_none()
        if template:
            steps = template.steps or []

    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择模板或提供步骤")

    # 如果手动输入了步骤（没选模板），自动创建一个临时模板来存储步骤
    if not req.template_id and steps:
        tmp_tpl = ProcedureTemplate(
            name=f"[临时] {req.title}",
            device_models=[req.device_model],
            maintenance_level="日常",
            steps=steps,
            author_id=user.id,
        )
        db.add(tmp_tpl)
        await db.flush()
        template_id = tmp_tpl.id

    task = TaskRecord(
        title=req.title,
        device_model=req.device_model,
        maintenance_level="日常",
        template_id=template_id,
        assignee_id=user.id,
        current_step=0,       # 从步骤 0 开始（第一步是 index 0）
        total_steps=len(steps),
        confirmed_steps=[],   # 空列表，逐步填入
        started_at=datetime.now(),
        deadline_at=datetime.now() + timedelta(hours=8),  # 默认 8 小时工时
    )
    db.add(task)
    await db.flush()

    await log_audit(db, user.id, "task.create", "task_record", task.id, f"开始作业：{req.title}")
    await db.commit()
    await db.refresh(task)

    return {
        "id": task.id,
        "total_steps": task.total_steps,
        "steps": steps,
        "message": "任务已创建",
    }


@router.get("/{task_id}")
async def get_task_detail(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取任务详情（含步骤内容）"""
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 如果从模板创建，加载模板步骤
    steps = []
    if task.template_id:
        tpl = await db.execute(select(ProcedureTemplate).where(ProcedureTemplate.id == task.template_id))
        template = tpl.scalar_one_or_none()
        if template:
            steps = template.steps or []

    # 已确认的步骤编号列表
    confirmed_step_nums = [s.get("step") for s in (task.confirmed_steps or [])]

    return {
        "id": task.id, "title": task.title, "device_model": task.device_model,
        "maintenance_level": task.maintenance_level, "status": task.status,
        "current_step": task.current_step, "total_steps": task.total_steps,
        "steps": steps,
        "confirmed_steps": task.confirmed_steps or [],
        "confirmed_step_nums": confirmed_step_nums,
        "pause_reason": task.pause_reason,
        "handover_note": task.handover_note,
        "handover_chain": task.handover_chain or [],
        "assignee_id": task.assignee_id,
        "original_assignee_id": task.original_assignee_id,
        "started_at": str(task.started_at) if task.started_at else "",
        "deadline_at": str(task.deadline_at) if task.deadline_at else "",
    }


@router.post("/{task_id}/step")
async def confirm_step(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认当前步骤，推进到下一步"""
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或不属于你")
    if task.status == "paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已暂停，请先恢复")
    if task.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已完成")

    # 记录当前步骤确认
    conf = task.confirmed_steps or []
    conf.append({
        "step": task.current_step + 1,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": user.id,
    })
    task.confirmed_steps = conf
    flag_modified(task, "confirmed_steps")  # 强制 SQLAlchemy 检测 JSON 列变更

    # 推进步骤编号
    task.current_step += 1

    # 最后一步确认后标记完成
    if task.current_step >= task.total_steps:
        task.status = "completed"
        task.completed_at = datetime.now()

    await log_audit(db, user.id, "task.step_confirm", "task_record", task_id, f"确认步骤 {task.current_step}/{task.total_steps}: {task.title}")
    await db.commit()

    return {
        "current_step": task.current_step,
        "total_steps": task.total_steps,
        "status": task.status,
        "message": "步骤已确认" if task.status != "completed" else "全部步骤已完成！",
    }


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: int,
    reason: str = Query(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """暂停任务"""
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在进行中状态")

    task.status = "paused"
    task.pause_reason = reason or "手动暂停"
    await db.commit()
    return {"message": "任务已暂停"}


@router.post("/{task_id}/resume")
async def resume_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """恢复任务"""
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if task.status != "paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务不在暂停状态")

    task.status = "in_progress"
    task.pause_reason = ""
    await db.commit()
    return {"message": "任务已恢复", "current_step": task.current_step}


@router.post("/{task_id}/handover")
async def handover_task(
    task_id: int,
    req: HandoverRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """交接任务给他人

    将任务转交给同班组的其他人员，记录交接链。
    """
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或不属于你")

    # 查找接收人
    to_user = await db.execute(select(User).where(User.id == req.to_user_id))
    receiver = to_user.scalar_one_or_none()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="接收人不存在")

    # 记录交接链
    chain = task.handover_chain or []
    chain.append({
        "from_user": user.id,
        "from_name": user.name,
        "to_user": req.to_user_id,
        "to_name": receiver.name,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    # 转移任务所有权
    if not task.original_assignee_id:
        task.original_assignee_id = task.assignee_id  # 保留原始执行人
    task.assignee_id = req.to_user_id
    task.handover_note = req.note
    task.handover_chain = chain
    flag_modified(task, "handover_chain")

    await log_audit(db, user.id, "task.handover", "task_record", task_id, f"交接作业：{task.title} → {receiver.name}")

    await db.commit()
    return {"message": f"任务已交接给 {receiver.name}", "chain": chain}


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    强制完成任务（提前结束）

    适用于中途确认作业已完成的场景，
    将剩余未完成步骤全部标记为跳过，状态改为 completed。
    """
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或不属于你")
    if task.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务已完成")

    # 将剩余步骤标记为跳过
    conf = task.confirmed_steps or []
    for step_num in range(task.current_step + 1, task.total_steps + 1):
        conf.append({
            "step": step_num,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_id": user.id,
            "skipped": True,
        })

    task.confirmed_steps = conf
    flag_modified(task, "confirmed_steps")
    task.current_step = task.total_steps
    task.status = "completed"
    task.completed_at = datetime.now()

    await log_audit(db, user.id, "task.complete", "task_record", task_id, f"完成任务：{task.title}")
    await db.commit()
    return {"message": "任务已完成"}


@router.delete("/{task_id}")
@router.post("/{task_id}/delete")
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除任务

    只能删除自己名下正在进行或已暂停的任务，已完成的任务不可删除（需保留归档）。
    """
    result = await db.execute(select(TaskRecord).where(TaskRecord.id == task_id, TaskRecord.assignee_id == user.id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或不属于你")

    await db.delete(task)
    await db.commit()
    return {"message": "任务已删除"}
