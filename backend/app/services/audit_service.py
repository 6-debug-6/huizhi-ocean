"""
审计日志服务：统一记录系统关键操作

提供 log() 辅助函数，在各 API 端点中调用，记录操作留痕。
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog


async def log_audit(
    db: AsyncSession,
    user_id: int,
    action: str,
    target_type: str,
    target_id: int = None,
    detail: str = "",
):
    """
    写入一条审计日志

    参数：
        db:          数据库会话
        user_id:     操作人 ID
        action:      操作类型（如 knowledge.create, review.approve）
        target_type: 操作对象类型（如 knowledge_entry, case_upload, ticket）
        target_id:   操作对象 ID
        detail:      操作详情描述
    """
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(log_entry)
