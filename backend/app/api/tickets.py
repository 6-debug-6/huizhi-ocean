"""
客服工单 API

端点：
    POST   /api/v1/tickets/                    — 用户提交工单
    GET    /api/v1/tickets/                    — 工单列表（用户看自己的，管理员看全部）
    GET    /api/v1/tickets/{id}                — 工单详情（含回复链）
    POST   /api/v1/tickets/{id}/reply          — 回复工单（管理员/专家）
    PUT    /api/v1/tickets/{id}/status          — 更新工单状态
    POST   /api/v1/tickets/{id}/to-knowledge   — 将工单转化为知识条目（管理员）

工单状态流转：
    PENDING → PROCESSING → REPLIED → RESOLVED → CLOSED

工单号格式：TK-YYYYMMDD-NNNN（日期+序号）
超时提醒：待处理超过 24 小时在仪表盘高亮
自动关闭：已解决 7 天后自动关闭
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.ticket import Ticket, TicketReply, TicketStatus
from app.models.knowledge import KnowledgeEntry, KnowledgeVersion, KnowledgeSource, KnowledgeStatus
from app.services.audit_service import log_audit
from app.schemas.ticket import (
    TicketCreate, TicketReplyCreate, TicketListItem, TicketDetail,
    TicketListResponse, ReplyItem, TicketStatusUpdate,
)

router = APIRouter()


def _generate_ticket_no(db_id: int) -> str:
    """生成工单号：TK-日期-序号"""
    today = datetime.now().strftime("%Y%m%d")
    return f"TK-{today}-{db_id:04d}"


# ==================== 用户端 ====================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    req: TicketCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    用户提交工单

    工单状态初始为 PENDING（待处理）。
    工单号在 flush 获取 ID 后自动生成。
    """
    # 创建工单
    ticket = Ticket(
        ticket_no="",  # flush 后回填
        title=req.title,
        description=req.description,
        images=req.images,
        creator_id=user.id,
        status=TicketStatus.PENDING,
    )
    db.add(ticket)
    await db.flush()  # 获取 ticket.id

    # 生成工单号并更新
    ticket.ticket_no = _generate_ticket_no(ticket.id)
    await log_audit(db, user.id, "ticket.create", "ticket", ticket.id, f"提交工单：{ticket.title}")
    await db.commit()
    await db.refresh(ticket)

    return {"id": ticket.id, "ticket_no": ticket.ticket_no, "message": "工单已提交"}


@router.get("/", response_model=TicketListResponse)
async def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str = Query("", alias="status"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    工单列表

    权限：
    - 一线人员：仅看到自己提交的工单
    - 管理员/专家：看到所有工单

    筛选：
    - status: 按状态筛选（空=全部）
    """
    query = select(Ticket)
    count_query = select(func.count(Ticket.id))

    if user.role == UserRole.WORKER:
        # 一线人员只能看自己的
        query = query.where(Ticket.creator_id == user.id)
        count_query = count_query.where(Ticket.creator_id == user.id)

    if status_filter:
        query = query.where(Ticket.status == status_filter)
        count_query = count_query.where(Ticket.status == status_filter)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页（最新在前）
    query = query.order_by(Ticket.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    tickets = result.scalars().all()

    items = []
    for t in tickets:
        # 查询用户名
        creator_name, assignee_name = "", ""
        if t.creator_id:
            u = await db.execute(select(User).where(User.id == t.creator_id))
            cu = u.scalar_one_or_none()
            if cu:
                creator_name = cu.name
        if t.assignee_id:
            u = await db.execute(select(User).where(User.id == t.assignee_id))
            au = u.scalar_one_or_none()
            if au:
                assignee_name = au.name

        # 查询回复数
        reply_count = await db.scalar(
            select(func.count(TicketReply.id)).where(TicketReply.ticket_id == t.id)
        ) or 0

        items.append(TicketListItem(
            id=t.id, ticket_no=t.ticket_no, title=t.title,
            creator_name=creator_name, creator_id=t.creator_id,
            assignee_name=assignee_name, status=t.status.value,
            reply_count=reply_count,
            created_at=t.created_at, updated_at=t.updated_at,
        ))

    return TicketListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket_detail(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    工单详情（含完整回复链）

    权限：
    - 工单提交者可查看自己的工单
    - 管理员/专家可查看所有工单
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

    # 权限校验
    if user.role == UserRole.WORKER and ticket.creator_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看此工单")

    # 查询用户名
    creator_name, assignee_name = "", ""
    if ticket.creator_id:
        u = await db.execute(select(User).where(User.id == ticket.creator_id))
        cu = u.scalar_one_or_none()
        if cu:
            creator_name = cu.name
    if ticket.assignee_id:
        u = await db.execute(select(User).where(User.id == ticket.assignee_id))
        au = u.scalar_one_or_none()
        if au:
            assignee_name = au.name

    # 查询回复链（按时间正序）
    reply_result = await db.execute(
        select(TicketReply).where(TicketReply.ticket_id == ticket_id).order_by(TicketReply.created_at)
    )
    replies = reply_result.scalars().all()

    reply_items = []
    for r in replies:
        replier_name = ""
        if r.replier_id:
            u = await db.execute(select(User).where(User.id == r.replier_id))
            ru = u.scalar_one_or_none()
            if ru:
                replier_name = ru.name
        reply_items.append(ReplyItem(
            id=r.id, replier_name=replier_name, replier_id=r.replier_id,
            content=r.content, attachments=r.attachments or [],
            created_at=r.created_at,
        ))

    return TicketDetail(
        id=ticket.id, ticket_no=ticket.ticket_no, title=ticket.title,
        description=ticket.description, images=ticket.images or [],
        creator_name=creator_name, creator_id=ticket.creator_id,
        assignee_name=assignee_name, assignee_id=ticket.assignee_id,
        status=ticket.status.value, replies=reply_items,
        created_at=ticket.created_at, updated_at=ticket.updated_at,
    )


# ==================== 管理端 ====================

@router.post("/{ticket_id}/reply")
async def reply_ticket(
    ticket_id: int,
    req: TicketReplyCreate,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.EXPERT)),
    db: AsyncSession = Depends(get_db),
):
    """
    回复工单（管理员/专家）

    首次回复时自动将工单状态从 PENDING 变为 PROCESSING。
    回复后状态变为 REPLIED。
    同时自动将回复人设为工单的 assignee。
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

    # 首次回复：接管工单
    if ticket.status == TicketStatus.PENDING:
        ticket.status = TicketStatus.PROCESSING
        ticket.assignee_id = user.id

    # 创建回复记录
    reply = TicketReply(
        ticket_id=ticket_id,
        replier_id=user.id,
        content=req.content,
        attachments=req.attachments,
    )
    db.add(reply)

    # 更新状态为已回复
    ticket.status = TicketStatus.REPLIED

    await log_audit(db, user.id, "ticket.reply", "ticket", ticket_id, f"回复工单 #{ticket.ticket_no}")
    await db.commit()
    return {"id": reply.id, "message": "回复已发送"}


@router.put("/{ticket_id}/status")
async def update_ticket_status(
    ticket_id: int,
    req: TicketStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新工单状态

    状态转换规则：
    - 用户可操作：RESOLVED（确认解决）
    - 管理员可操作：PROCESSING（接管）、CLOSED（关闭）
    - 系统自动：7 天后 RESOLVED → CLOSED

    若传入 assignee_id，则同时指定处理人。
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

    # 权限校验
    if req.status == "resolved":
        # 只能工单提交者确认解决
        if ticket.creator_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有工单提交者可以标记为已解决")
        ticket.status = TicketStatus.RESOLVED
    elif req.status in ("processing", "closed"):
        # 仅管理员/专家可操作
        if user.role not in (UserRole.ADMIN, UserRole.EXPERT):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        if req.status == "processing":
            ticket.status = TicketStatus.PROCESSING
        else:
            ticket.status = TicketStatus.CLOSED
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的状态: {req.status}")

    if req.assignee_id:
        ticket.assignee_id = req.assignee_id

    await log_audit(db, user.id, f"ticket.{req.status}", "ticket", ticket_id, f"工单 #{ticket.ticket_no} 状态更新为 {req.status}")
    await db.commit()
    return {"message": f"工单状态已更新为 {req.status}"}


@router.post("/{ticket_id}/to-knowledge")
async def ticket_to_knowledge(
    ticket_id: int,
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.EXPERT)),
    db: AsyncSession = Depends(get_db),
):
    """
    将已解决的工单转化为知识条目

    转化规则：
    1. 工单标题 → 知识条目标题
    2. 工单描述 + 所有回复 → 知识条目内容
    3. 来源标记为 ticket
    4. 状态为 draft（管理员后续可编辑发布）

    只有 RESOLVED 或 CLOSED 状态的工单可以转化。
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")

    if ticket.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只有已解决或已关闭的工单才能转化为知识条目",
        )

    # 聚合工单内容和所有回复
    content_parts = [f"## 问题描述\n{ticket.description}"]
    reply_result = await db.execute(
        select(TicketReply).where(TicketReply.ticket_id == ticket_id).order_by(TicketReply.created_at)
    )
    for r in reply_result.scalars().all():
        replier_name = "管理员"
        if r.replier_id:
            u = await db.execute(select(User).where(User.id == r.replier_id))
            ru = u.scalar_one_or_none()
            if ru:
                replier_name = ru.name
        content_parts.append(f"## {replier_name}的回复\n{r.content}")

    entry = KnowledgeEntry(
        title=ticket.title,
        content="\n\n".join(content_parts),
        summary=ticket.title,
        source=KnowledgeSource.TICKET,
        source_ref=f"工单 {ticket.ticket_no}",
        device_models=[],
        fault_tags=[],
        is_procedure=False,
        author_id=ticket.creator_id,
        current_version="V1.0",
        status=KnowledgeStatus.DRAFT,  # 草稿状态，管理员需进一步编辑
    )
    db.add(entry)
    await db.flush()

    version = KnowledgeVersion(
        entry_id=entry.id, version="V1.0", version_num=1,
        content=entry.content,
        change_summary="从客服工单转化生成",
        editor_id=user.id,
    )
    db.add(version)
    await log_audit(db, user.id, "ticket.to_knowledge", "ticket", ticket_id, f"工单 #{ticket.ticket_no} 转化为知识条目 #{entry.id}")
    await db.commit()

    return {"id": entry.id, "message": "工单已转化为知识条目草稿，请在知识库管理中编辑发布"}
