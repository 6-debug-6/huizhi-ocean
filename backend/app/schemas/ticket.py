"""
客服工单模块的 Pydantic 数据模型

工单制客服（非实时聊天）：
- 用户提交问题 → 管理员接管回复 → 用户确认解决
- 已解决的工单可沉淀为知识条目
- 24 小时未回复的工单自动高亮提醒
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TicketCreate(BaseModel):
    """创建工单请求体"""
    title: str = Field(..., min_length=1, max_length=300, description="问题标题")
    description: str = Field(..., min_length=1, description="问题详细描述")
    images: list[str] = Field(default_factory=list, description="辅助图片路径列表")  # 可选，上传图片后的 URL 列表


class TicketReplyCreate(BaseModel):
    """工单回复请求体"""
    content: str = Field(..., min_length=1, description="回复内容（支持富文本）")
    attachments: list[str] = Field(default_factory=list, description="附件路径列表")


class TicketListItem(BaseModel):
    """工单列表项（用于列表页展示）"""
    id: int
    ticket_no: str              # 工单号：TK-20250610-0001
    title: str                  # 问题标题
    creator_name: str = ""      # 提交人姓名
    creator_id: int             # 提交人 ID
    assignee_name: str = ""     # 指派处理人姓名
    status: str                 # 工单状态
    reply_count: int = 0        # 回复条数
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketDetail(BaseModel):
    """工单详情（含完整内容和回复链）"""
    id: int
    ticket_no: str
    title: str
    description: str                          # 问题完整描述
    images: list[str]                         # 辅助图片
    creator_name: str = ""
    creator_id: int
    assignee_name: str = ""
    assignee_id: Optional[int]
    status: str
    replies: list["ReplyItem"] = []           # 回复列表（按时间排序）
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReplyItem(BaseModel):
    """工单中的单条回复"""
    id: int
    replier_name: str = ""       # 回复人姓名
    replier_id: int              # 回复人 ID
    content: str                 # 回复内容
    attachments: list[str]       # 附件路径
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    """分页工单列表响应"""
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class TicketStatusUpdate(BaseModel):
    """工单状态更新请求体"""
    status: str = Field(..., description="目标状态: processing / replied / resolved / closed")
    assignee_id: Optional[int] = Field(None, description="指派处理人 ID（processing 时可选）")
