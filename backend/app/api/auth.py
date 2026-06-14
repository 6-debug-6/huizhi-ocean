"""
用户认证 API

端点：
    POST /api/v1/auth/register                — 用户注册
    POST /api/v1/auth/login                   — 用户登录，返回 JWT 令牌
    GET  /api/v1/auth/me                      — 获取当前登录用户信息
    POST /api/v1/auth/users/{id}/reset-password — 管理员重置用户密码
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User, UserRole, UserStatus
from app.models.audit import AuditLog
from app.services.audit_service import log_audit
from app.schemas.auth import RegisterRequest, LoginRequest, LoginResponse, UserInfo, PasswordResetRequest

def _format_time(dt: datetime | None) -> str:
    """
    格式化数据库时间为显示字符串

    SQLite 存储的是本地时间（CST），但 DateTime(timezone=True) 让 SQLAlchemy
    将其误读为 UTC。实际上存储的值就是正确的本地时间，直接取前 19 位即可，
    不做时区转换，避免二次偏移。
    """
    if not dt:
        return ""
    # 直接取 datetime 的字符串表示前 19 位（YYYY-MM-DD HH:MM:SS）
    return str(dt)[:19]

router = APIRouter()


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    用户注册

    新用户默认角色为 WORKER（一线人员），状态为 PENDING（待审核）。
    注册后需等待管理员审核通过方可登录。
    用户名重复时返回 409 冲突错误。
    """
    # 检查用户名是否已被占用
    existing = await db.execute(select(User).where(User.username == req.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")

    # 创建用户记录，密码使用 bcrypt 哈希后存储
    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),  # 不存储明文密码
        name=req.name,
        employee_id=req.employee_id,
        team=req.team,
        role=UserRole.WORKER,         # 固定为一线人员角色
        status=UserStatus.PENDING,    # 需管理员审核后激活
    )
    db.add(user)
    await db.commit()
    return {"message": "注册成功，请等待管理员审核"}


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    用户登录

    验证用户名和密码，返回 JWT 访问令牌。
    令牌包含用户 ID 和角色信息，有效期 8 小时（由配置控制）。
    登录失败条件：
        - 用户名或密码错误 → 401
        - 账号尚未审核通过 → 403
        - 账号已被禁用 → 403
    """
    # 按用户名查找用户
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    # 验证密码（使用固定错误信息防止用户名枚举攻击）
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    # 检查账号状态
    if user.status == UserStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号尚未通过审核")
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    # 签发 JWT 令牌，载荷包含用户 ID（sub）和角色（role）
    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

    return LoginResponse(
        access_token=token,
        user=UserInfo.model_validate(user),  # ORM 对象 → Pydantic 模型
    )


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息

    依赖 get_current_user 解析 JWT 令牌并查询数据库。
    可用于：前端页面刷新后恢复用户状态、验证令牌有效性。
    """
    return UserInfo.model_validate(user)


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    req: PasswordResetRequest,
    admin: User = Depends(require_admin),   # 仅管理员可操作
    db: AsyncSession = Depends(get_db),
):
    """
    管理员重置用户密码

    仅管理员角色可调用（require_admin 依赖校验）。
    用户忘记密码时联系管理员，管理员使用此接口重置。
    用户下次登录时使用新密码。
    """
    # 查找目标用户
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 更新密码哈希
    target_user.hashed_password = hash_password(req.new_password)
    await db.commit()
    return {"message": "密码已重置"}


@router.get("/users")
async def list_users(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有用户列表（仅管理员）

    返回所有注册用户的信息，包括待审核和已禁用的用户。
    不返回密码哈希等敏感字段。
    """
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserInfo.model_validate(u) for u in users]


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    status: str = Query(..., description="目标状态: active / disabled"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    审核/启用/禁用用户（仅管理员）

    status 可选值：
        - active:   审核通过（从 pending 变为 active）
        - disabled: 禁用用户
    """
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if status == "active":
        target_user.status = UserStatus.ACTIVE
        action_detail = f"审核通过用户 {target_user.name}({target_user.username})"
    elif status == "disabled":
        target_user.status = UserStatus.DISABLED
        action_detail = f"禁用用户 {target_user.name}({target_user.username})"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的状态")

    # 写入审计日志
    log = AuditLog(
        user_id=admin.id,
        action="user.status_change",
        target_type="user",
        target_id=user_id,
        detail=action_detail,
    )
    db.add(log)

    await db.commit()
    return {"message": f"用户状态已更新为 {status}"}


@router.delete("/users/{user_id}")
@router.post("/users/{user_id}/delete")
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除用户（仅管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if target.username == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除超级管理员")
    await db.delete(target)
    await log_audit(db, admin.id, "user.delete", "user", user_id, f"删除用户：{target.name}")
    await db.commit()
    return {"message": "用户已删除"}


@router.delete("/logs/{log_id}")
@router.post("/logs/{log_id}/delete")
async def delete_log(
    log_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """删除单条审计日志（仅管理员）"""
    result = await db.execute(select(AuditLog).where(AuditLog.id == log_id))
    log_entry = result.scalar_one_or_none()
    if not log_entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="日志不存在")
    await db.delete(log_entry)
    await db.commit()
    return {"message": "日志已删除"}


@router.get("/logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    获取操作审计日志（仅管理员）

    按时间倒序返回系统关键操作记录。
    """
    count_result = await db.execute(select(func.count(AuditLog.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    logs = result.scalars().all()

    items = []
    for log in logs:
        username = ""
        if log.user_id:
            u = await db.execute(select(User).where(User.id == log.user_id))
            user_obj = u.scalar_one_or_none()
            if user_obj:
                username = user_obj.name
        items.append({
            "id": log.id,
            "user_name": username,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip_address": log.ip_address or "",
            "created_at": _format_time(log.created_at),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}
