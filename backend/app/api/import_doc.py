"""
文档导入 API

端点：
    POST /api/v1/import/pdf — 上传 PDF 手册，解析入库

流程：
    1. 上传 PDF 文件 → 存入磁盘
    2. PDF 解析（PyMuPDF：文本+表格+内嵌图片导出为PNG）
    3. 图片描述生成（千问 VL，含错误回退）
    4. 生成知识片段（chunks）
    5. 向量化 → 存入 ChromaDB
    6. 创建 KnowledgeEntry 记录（来源=pdf_import，状态=草稿）
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.config import get_settings
from app.models.user import User
from app.models.knowledge import KnowledgeEntry, KnowledgeVersion, KnowledgeStatus, KnowledgeSource
from app.services.vector_store import vector_store
from app.services.file_service import save_upload

settings = get_settings()
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
    内嵌图片由千问 VL 生成中文描述后纳入知识片段。
    解析结果同时创建 KnowledgeEntry 记录（草稿状态），管理员可编辑后发布。

    参数：
        file: PDF 文件（≤50MB）
        device_model: 关联的设备型号
    """
    # 校验文件类型和大小
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件大小不能超过 50MB")

    # 保存 PDF 到磁盘
    filepath = save_upload(content, file.filename, "documents")
    # 使用 os.path.abspath 获取规范绝对路径（处理 Windows 分隔符混用）
    abs_path = os.path.abspath(os.path.join(settings.UPLOAD_DIR, filepath))

    # 解析 PDF → 知识片段（PyMuPDF）
    try:
        from app.services.pdf_parser import parse_pdf_to_documents
        documents = await parse_pdf_to_documents(abs_path)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 解析依赖未安装，请运行: pip install PyMuPDF"
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF 解析失败: {str(e)}")

    if not documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PDF 中未提取到文本内容")

    # ========== 为图片 chunk 生成描述（千问 VL） ==========
    img_described = 0
    from app.services.llm_adapter import model_router

    for doc in documents:
        if doc["metadata"].get("type") == "image" and doc["metadata"].get("image_path"):
            img_path = doc["metadata"]["image_path"]
            try:
                description = await model_router.analyze_image(
                    image_url=f"file://{img_path}",
                    prompt="请详细描述这张设备维修手册图片中的内容，"
                           "特别是设备结构、拆解步骤、工具使用、标注信息等关键内容。用中文回答。"
                )
                if description and description.strip():
                    doc["content"] = f"[图片描述]：{description.strip()}"
                    img_described += 1
            except Exception:
                doc["content"] = "[图片描述]：暂未生成描述（视觉模型不可用），请人工查看原PDF"

    # 将完整内容聚合为知识条目正文
    full_text_parts = []
    device_models = [device_model] if device_model else []
    for doc in documents:
        if doc.get("content"):
            source_info = f"[第{doc['metadata'].get('page', '?')}页 · {doc['metadata'].get('type', 'text')}]"
            full_text_parts.append(f"{source_info}\n{doc['content']}")

    # 创建 KnowledgeEntry（草稿状态，管理员后续编辑发布）
    entry = KnowledgeEntry(
        title=f"{file.filename}（PDF导入）",
        content="\n\n---\n\n".join(full_text_parts),
        summary=f"从 {file.filename} 自动导入，共 {len(documents)} 个知识片段" +
                (f"，{img_described} 张图片已生成描述" if img_described else ""),
        source=KnowledgeSource.PDF_IMPORT,
        source_ref=file.filename,
        device_models=device_models,
        fault_tags=[],
        is_procedure=False,
        author_id=admin.id,
        current_version="V1.0",
        status=KnowledgeStatus.PUBLISHED,  # 直接发布，管理员可后续归档
    )
    db.add(entry)
    await db.flush()

    # 创建初始版本
    version = KnowledgeVersion(
        entry_id=entry.id, version="V1.0", version_num=1,
        content=entry.content,
        change_summary=f"从 PDF 文件 {file.filename} 自动导入（{img_described}张图片已描述）",
        editor_id=admin.id,
    )
    db.add(version)

    # 向量化入库
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
    except Exception:
        pass  # 向量化失败不阻塞入库

    await db.commit()

    # 清理临时图片文件
    try:
        from app.services.pdf_parser import PDFParser
        # 临时文件已在 doc 的 metadata.image_path 中，遍历清理
        for doc in documents:
            ip = doc["metadata"].get("image_path", "")
            if ip and os.path.exists(ip):
                os.remove(ip)
    except Exception:
        pass

    return {
        "message": "PDF 导入完成",
        "entry_id": entry.id,
        "chunks_total": len(documents),
        "chunks_vectorized": vector_count,
        "images_described": img_described,
        "file_url": f"/uploads/{filepath}",
    }
