"""
文档导入 API

端点：
    POST /api/v1/import/pdf — 上传 PDF 手册，解析入库

流程：
    1. 上传 PDF 文件 → 存入磁盘
    2. PDF 解析（文本+表格+图片区域提取）
    3. 生成知识片段（chunks）
    4. 向量化 → 存入 ChromaDB
    5. 创建 KnowledgeEntry 记录（来源=pdf_import）
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.user import User
from app.models.knowledge import KnowledgeEntry, KnowledgeVersion, KnowledgeStatus, KnowledgeSource
from app.services.vector_store import vector_store
from app.services.file_service import save_upload

router = APIRouter()


@router.post("/pdf")
async def import_pdf(
    file: UploadFile = File(...),
    device_model: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    导入 PDF 检修手册

    将 PDF 文件解析为知识片段，向量化后存入知识库和向量数据库。
    解析结果同时创建 KnowledgeEntry 记录，管理员可在知识库管理中查看和编辑。

    参数：
        file: PDF 文件
        device_model: 关联的设备型号（如"XX型柴油发动机"）
    """
    # 校验文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件大小不能超过 50MB")

    # 保存 PDF 到磁盘
    filepath = save_upload(content, file.filename, "documents")
    abs_path = os.path.join("data/uploads", filepath)

    # 解析 PDF → 知识片段（延迟导入 pdfplumber 依赖）
    try:
        from app.services.pdf_parser import parse_pdf_to_documents
        documents = await parse_pdf_to_documents(abs_path)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 解析依赖未安装，请运行: pip install pdfplumber"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF 解析失败: {str(e)}")

    if not documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF 中未提取到文本内容")

    # 将完整内容聚合为知识条目正文
    full_text_parts = []
    device_models = [device_model] if device_model else []
    for doc in documents:
        if doc.get("content"):
            source_info = f"[第{doc['metadata'].get('page', '?')}页]"
            full_text_parts.append(f"{source_info}\n{doc['content']}")

    # 创建 KnowledgeEntry（管理员后续可编辑优化）
    entry = KnowledgeEntry(
        title=f"{file.filename}（PDF导入）",
        content="\n\n---\n\n".join(full_text_parts),
        summary=f"从 {file.filename} 自动导入，共 {len(documents)} 个知识片段",
        source=KnowledgeSource.PDF_IMPORT,
        source_ref=file.filename,
        device_models=device_models,
        fault_tags=[],
        is_procedure=False,
        author_id=admin.id,
        current_version="V1.0",
        status=KnowledgeStatus.DRAFT,  # 草稿状态，管理员审核后发布
    )
    db.add(entry)
    await db.flush()

    # 创建初始版本
    version = KnowledgeVersion(
        entry_id=entry.id, version="V1.0", version_num=1,
        content=entry.content,
        change_summary=f"从 PDF 文件 {file.filename} 自动导入",
        editor_id=admin.id,
    )
    db.add(version)

    # 向量化入库（用知识条目 ID 作为前缀，方便关联）
    vector_docs = []
    for doc in documents:
        if doc.get("content"):
            vector_docs.append({
                "id": f"pdf_entry{entry.id}_{doc['id']}",
                "content": doc["content"],
                "metadata": {
                    "page": doc["metadata"].get("page", 0),
                    "type": doc["metadata"].get("type", "text"),
                    "source_file": file.filename,
                    "entry_id": str(entry.id),
                },
            })

    vector_count = 0
    try:
        vector_count = vector_store.add_documents(vector_docs)
    except Exception as e:
        # 向量化失败不阻塞入库
        pass

    await db.commit()

    return {
        "message": "PDF 导入完成",
        "entry_id": entry.id,
        "chunks_total": len(documents),
        "chunks_vectorized": vector_count,
        "file_url": f"/uploads/{filepath}",
    }
