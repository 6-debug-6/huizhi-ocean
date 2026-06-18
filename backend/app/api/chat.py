"""
AI 对话 API：RAG 检索增强生成 + 会话管理

端点：
    POST  /api/v1/conversations                   — 创建新对话
    GET   /api/v1/conversations                   — 获取用户的对话列表
    GET   /api/v1/conversations/{id}              — 获取对话详情（含消息历史）
    POST  /api/v1/chat                            — 发送消息（RAG 链路）
    POST  /api/v1/conversations/{id}/feedback     — 提交反馈（对某条 AI 回复的评价）

RAG 流程（send_message）：
    1. 验证对话归属（防止越权访问）
    2. 处理图片（如有 → 千问 VL 视觉分析）
    3. 检索背景知识（向量库搜索 → 拼接为上下文）
    4. 获取对话历史（最近 10 轮）
    5. 拼装 System Prompt（模板化，注入知识上下文+历史+设备/步骤信息）
    6. 调用大模型生成回复
    7. 解析结构化回复
    8. 保存消息 → 返回

反馈收集：
    - useful/partial/useless 三个级别
    - partial 和 useless 时可填写修正内容
    - 连续两次 useless → 提示用户提交客服工单
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.services.llm_adapter import model_router
from app.services.vector_store import vector_store
from app.services.audit_service import log_audit
from pydantic import BaseModel

router = APIRouter()

# 检修场景专用 Prompt（结构化回答）
RAG_SYSTEM_PROMPT = """你是一个设备检修专家助手。回答时按以下结构组织：
1. 问题分析（对用户描述的现象进行分析）
2. 可能原因（列出1-3个最可能的原因，按概率排序）
3. 推荐方案（针对每个原因给出具体操作步骤）
4. 参考来源（列出引用的知识来源）

当前上下文（如有）：设备型号={device_model}，当前作业步骤={task_step}
遵守合规要求：所有操作建议必须包含安全提醒。

已知相关知识（从知识库检索获得）：
{knowledge_context}

对话历史：
{history}

用户消息：{user_message}"""

# 日常对话 Prompt（闲聊、功能介绍、非检修类问题）
CASUAL_PROMPT = """你是一个友好、乐于助人的设备检修助手。请用自然随和的语气直接回答用户的问题。

注意：
- 不要使用"分析/可能原因/推荐方案/参考来源"的结构化格式
- 不要输出列表式的检修步骤，除非用户明确问到具体故障
- 保持对话感，像和同事聊天一样
- 如果用户问的是知识库相关内容，可以提及知识库中有相应的资料

{user_message}"""

class FeedbackRequest(BaseModel):
    feedback: str  # useful / partial / useless
    comment: str = ""
    message_id: int | None = None  # 指定反馈的消息ID，不传则取该对话最新assistant消息


# ---- 会话管理 ----

@router.post("/conversations")
async def create_conversation(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(user_id=user.id)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {"id": conv.id, "title": conv.title, "created_at": str(conv.created_at)}


@router.get("/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return [{"id": c.id, "title": c.title, "created_at": str(c.created_at), "updated_at": str(c.updated_at)} for c in convs]


@router.get("/conversations/my-feedback")
async def get_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的 AI 回复修正/反馈历史"""
    conv_result = await db.execute(
        select(Conversation.id).where(Conversation.user_id == user.id)
    )
    conv_ids = [row[0] for row in conv_result.all()]
    if not conv_ids:
        return {"items": [], "total": 0}

    msg_query = (
        select(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.role == "assistant",
            Message.feedback != "",
            Message.feedback.isnot(None),
        )
        .order_by(Message.created_at.desc())
    )

    count_result = await db.execute(
        select(func.count()).select_from(msg_query.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        msg_query.offset((page - 1) * page_size).limit(page_size)
    )
    messages = result.scalars().all()

    items = []
    for msg in messages:
        prev_result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == msg.conversation_id,
                Message.role == "user",
                Message.created_at < msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_msg = prev_result.scalar_one_or_none()

        items.append({
            "id": msg.id,
            "question": (prev_msg.content[:200] if prev_msg else ""),
            "ai_reply": msg.content[:300],
            "feedback": msg.feedback,
            "comment": msg.feedback_comment or "",
            "created_at": str(msg.created_at) if msg.created_at else "",
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/admin/feedback")
async def get_all_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feedback_type: str = Query("", description="按反馈类型筛选：useful / partial / useless"),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    管理员查看所有用户的AI回复反馈（跨所有对话）

    支持按反馈类型筛选，返回用户姓名和完整的问题/AI回复内容。
    管理员可据此发现知识库盲区、模型回答质量问题，并采取对应措施。
    """
    from app.models.user import User as UserModel

    # 构建查询：所有有反馈的 assistant 消息
    conditions = [Message.role == "assistant", Message.feedback != "", Message.feedback.isnot(None)]
    if feedback_type:
        conditions.append(Message.feedback == feedback_type)

    msg_query = select(Message).where(*conditions)

    # 总数
    count_result = await db.execute(
        select(func.count()).select_from(msg_query.subquery())
    )
    total = count_result.scalar() or 0

    # 分页
    result = await db.execute(
        msg_query.order_by(Message.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    messages = result.scalars().all()

    items = []
    for msg in messages:
        # 查找该消息所属对话和用户
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == msg.conversation_id)
        )
        conv = conv_result.scalar_one_or_none()
        user_name = ""
        user_id = None
        if conv:
            user_id = conv.user_id
            u_result = await db.execute(select(UserModel).where(UserModel.id == conv.user_id))
            u = u_result.scalar_one_or_none()
            if u:
                user_name = u.name

        # 查找该消息之前的用户提问
        prev_result = await db.execute(
            select(Message)
            .where(
                Message.conversation_id == msg.conversation_id,
                Message.role == "user",
                Message.created_at < msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        prev_msg = prev_result.scalar_one_or_none()

        items.append({
            "id": msg.id,
            "message_id": msg.id,
            "conversation_id": msg.conversation_id,
            "user_name": user_name,
            "user_id": user_id,
            "question": (prev_msg.content[:300] if prev_msg else ""),
            "ai_reply": msg.content[:500],
            "feedback": msg.feedback,
            "comment": msg.feedback_comment or "",
            "created_at": str(msg.created_at) if msg.created_at else "",
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/admin/feedback/{message_id}/to-knowledge")
async def feedback_to_knowledge(
    message_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    将 AI 反馈消息转化为知识条目（管理员）

    转化规则：
    1. 原用户提问 → 知识条目标题
    2. AI 回复 + 用户修正建议 → 知识条目内容
    3. 来源标记为 ai_feedback
    4. 状态为 draft（管理员后续可编辑发布）
    """
    # 获取反馈消息
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.role == "assistant", Message.feedback != "", Message.feedback.isnot(None))
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在或无反馈记录")

    # 获取用户提问
    prev_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == msg.conversation_id, Message.role == "user", Message.created_at < msg.created_at)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    prev_msg = prev_result.scalar_one_or_none()
    question = prev_msg.content if prev_msg else "未知问题"

    # 获取用户信息
    conv_result = await db.execute(select(Conversation).where(Conversation.id == msg.conversation_id))
    conv = conv_result.scalar_one_or_none()
    author_id = None
    if conv:
        author_id = conv.user_id

    # 构建知识内容
    content_parts = [f"## 用户提问\n{question}"]
    content_parts.append(f"## AI 回复\n{msg.content}")
    if msg.feedback_comment:
        content_parts.append(f"## 用户修正建议\n{msg.feedback_comment}")

    from app.models.knowledge import KnowledgeEntry, KnowledgeVersion, KnowledgeSource, KnowledgeStatus
    import logging
    logger = logging.getLogger(__name__)

    try:
        entry = KnowledgeEntry(
            title=question[:200],
            content="\n\n".join(content_parts),
            summary=question[:200],
            source=KnowledgeSource.AI_FEEDBACK,
            source_ref=f"AI反馈 #{message_id}",
            device_models=[],
            fault_tags=[],
            is_procedure=False,
            author_id=author_id,
            current_version="V1.0",
            status=KnowledgeStatus.DRAFT,
        )
        db.add(entry)
        await db.flush()

        version = KnowledgeVersion(
            entry_id=entry.id, version="V1.0", version_num=1,
            content=entry.content,
            change_summary="从AI反馈转化生成",
            editor_id=user.id,
        )
        db.add(version)
        await log_audit(db, user.id, "feedback.to_knowledge", "message", message_id, f"AI反馈 #{message_id} 转化为知识条目 #{entry.id}")
        await db.commit()

        return {"id": entry.id, "message": "AI反馈已转化为知识条目草稿，请在知识库管理中编辑发布"}
    except Exception as e:
        logger.exception("AI反馈转化知识条目失败: %s", e)
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"转化失败: {str(e)}")


@router.delete("/admin/feedback/{message_id}")
@router.post("/admin/feedback/{message_id}/delete")
async def delete_feedback(
    message_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    删除 AI 反馈记录（仅管理员）

    删除单条消息的反馈标记（feedback 和 feedback_comment 字段清空），消息本身保留。
    用于清理无效或误操作产生的反馈数据。
    """
    result = await db.execute(
        select(Message).where(Message.id == message_id, Message.role == "assistant")
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")

    msg.feedback = ""
    msg.feedback_comment = ""
    await log_audit(db, user.id, "feedback.delete", "message", message_id, f"清除AI反馈 #{message_id}")
    await db.commit()
    return {"message": "反馈记录已删除"}


@router.get("/conversations/{conv_id}")
async def get_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    msg_result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "structured_reply": m.structured_reply,
                "feedback": m.feedback,
                "image_urls": m.image_urls,
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
    }


# ---- 对话 ----

@router.post("/chat")
async def send_message(
    message: str = Form(...),
    conversation_id: int = Form(...),
    image: UploadFile | None = File(None),
    device_model: str = Form(""),
    task_step: str = Form(""),
    chat_mode: str = Form("rag"),  # rag(检修模式) / casual(闲聊模式)
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证对话归属
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    # 处理图片：转为 base64 data URL（DashScope 不支持 file:// 路径）
    image_urls = []
    has_image = False
    if image:
        import base64
        content = await image.read()
        content_type = image.content_type or "image/png"
        b64 = base64.b64encode(content).decode("utf-8")
        data_url = f"data:{content_type};base64,{b64}"
        image_urls.append(data_url)
        has_image = True

    # 检索背景知识（控制总量避免挤占生成空间导致截断）
    knowledge_context = ""
    try:
        search_results = await asyncio.wait_for(
            asyncio.to_thread(vector_store.search, message, 5),  # Top 5
            timeout=5.0
        )
        # 每条最多600字符，总共约3000字符（留足空间给生成）
        knowledge_context = "\n\n---\n\n".join([
            f"[来源: {r['metadata'].get('source_file', '未知')}]\n{r['content'][:600]}"
            for r in search_results
        ])
    except (asyncio.TimeoutError, Exception):
        pass  # 向量库不可用时跳过背景知识增强，大模型直接回答

    # 构建消息历史（最近10轮）
    hist_result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(20)
    )
    recent_messages = list(reversed(hist_result.scalars().all()))
    history_text = "\n".join([
        f"{'用户' if m.role == 'user' else '助手'}: {m.content[:200]}"
        for m in recent_messages
    ])

    # 判断意图：前端传 chat_mode 优先，无图片时尊重用户选择
    casual = (chat_mode == "casual" and not has_image)

    # 构建 Prompt（闲聊跳过向量检索，直接用对话式 Prompt）
    if casual:
        system_prompt = CASUAL_PROMPT.format(user_message=message)
    else:
        system_prompt = RAG_SYSTEM_PROMPT.format(
            device_model=device_model or "未指定",
            task_step=task_step or "无",
            knowledge_context=knowledge_context or "未找到相关知识",
            history=history_text or "无历史",
            user_message=message,
        )

    # 调用大模型
    llm_messages = [{"role": "system", "content": system_prompt}]
    if image_urls and has_image:
        llm_messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_urls[0]}},
                {"type": "text", "text": message},
            ],
        })
    else:
        llm_messages.append({"role": "user", "content": message})

    # 调用大模型（带重试，处理临时性 API 故障）
    reply = ""
    last_error = ""
    for attempt in range(3):
        try:
            reply = await asyncio.wait_for(
                model_router.chat(llm_messages, has_image=has_image,
                                  temperature=0.5 if casual else 0.3),
                timeout=90.0,
            )
            break
        except asyncio.TimeoutError:
            last_error = "timeout"
            continue
        except Exception as e:
            last_error = str(e)[:200]
            # HTTP 4xx 不重试（认证/参数错误），5xx 和网络错误重试
            if "401" in str(e) or "403" in str(e) or "413" in str(e):
                break
            # 短暂等待后重试
            await asyncio.sleep(0.5 * (attempt + 1))
            continue

    if not reply:
        if last_error == "timeout":
            reply = "AI 服务响应超时，请稍后重试。若问题持续，可提交客服工单寻求人工帮助。"
        else:
            reply = "AI 服务暂时不可用，请稍后重试。若需紧急帮助，可提交客服工单。"

    # 解析结构化回复（闲聊模式跳过，避免将"分析"等日常用语误解析为检修结构）
    structured = {} if casual else _parse_structured_reply(reply)

    # 保存消息
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=message,
        image_urls=image_urls if image_urls else [],
    )
    db.add(user_msg)

    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=reply,
        structured_reply=structured,
    )
    db.add(assistant_msg)

    # 更新对话标题（首次对话用首条用户消息）
    if not recent_messages:
        conv.title = message[:50] + ("..." if len(message) > 50 else "")
    conv.updated_at = func.now()

    await db.commit()
    await db.refresh(assistant_msg)

    return {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": reply,
        "structured_reply": structured,
        "conversation_id": conversation_id,
        "created_at": str(assistant_msg.created_at),
    }


@router.post("/conversations/{conv_id}/feedback")
async def submit_feedback(
    conv_id: int,
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 获取指定消息或最后一条 assistant 消息
    if req.message_id:
        result = await db.execute(
            select(Message).where(Message.id == req.message_id, Message.conversation_id == conv_id, Message.role == "assistant")
        )
    else:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
    last_msg = result.scalar_one_or_none()
    if not last_msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="没有可反馈的消息")

    last_msg.feedback = req.feedback
    last_msg.feedback_comment = req.comment
    await db.commit()

    # 连续两次无用 → 提示提交工单
    useless_count = 0
    if req.feedback == "useless":
        recent_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.role == "assistant")
            .order_by(Message.created_at.desc())
            .limit(5)
        )
        for m in recent_result.scalars().all():
            if m.feedback == "useless":
                useless_count += 1
            else:
                break

    return {
        "message": "反馈已提交",
        "suggest_ticket": useless_count >= 2,
    }


@router.delete("/conversations/{conv_id}")
@router.post("/conversations/{conv_id}/delete")
async def delete_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    删除对话（仅对话所有者可操作）

    同时删除对话下的所有消息记录。
    """
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    # 删除所有关联消息
    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(Message).where(Message.conversation_id == conv_id))

    # 删除对话
    await db.delete(conv)
    await db.commit()
    return {"message": "对话已删除"}


@router.put("/conversations/{conv_id}")
async def rename_conversation(
    conv_id: int,
    title: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重命名对话（仅对话所有者可操作）
    """
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在")

    conv.title = title
    await db.commit()
    return {"message": "对话已重命名"}

def _parse_structured_reply(reply: str) -> dict:
    """尝试解析 AI 回复中的结构化内容"""
    result = {"analysis": "", "causes": [], "solutions": [], "sources": []}
    # 简单按段落标题解析
    current_section = ""
    for line in reply.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "问题分析" in line or "分析" in line:
            current_section = "analysis"
            continue
        if "可能原因" in line or "原因" in line:
            current_section = "causes"
            continue
        if "推荐方案" in line or "方案" in line:
            current_section = "solutions"
            continue
        if "参考来源" in line or "来源" in line:
            current_section = "sources"
            continue

        if current_section == "analysis" and not result["analysis"]:
            result["analysis"] = line
        elif current_section == "causes":
            result["causes"].append(line)
        elif current_section == "solutions":
            result["solutions"].append(line)
        elif current_section == "sources":
            result["sources"].append(line)

    result["causes"] = result["causes"][:3]
    result["solutions"] = result["solutions"][:5]
    return result
