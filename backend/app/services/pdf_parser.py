"""
PDF 离线解析管线

将 PDF 检修手册解析为结构化知识片段，供向量化入库。

解析流程：
    1. 页面拆分：PDF → 逐页处理
    2. 多模态提取：文本（段落切分）+ 表格（结构保留）+ 内嵌图片（导出为 PNG）
    3. 知识分片（Chunking）：按段落/表格/图片类型生成独立片段
    4. 输出文档列表：每片含内容 + 元信息，可直接送入向量库

依赖：
    - PyMuPDF (fitz): PDF 解析引擎，支持文本、表格提取和内嵌图片导出
    - 视觉模型（千问 VL）：图片区域的描述生成在 import_doc 层调用

设计说明：
    - 这是一个离线（batch）处理管线，不暴露为实时 API
    - 解析结果先存入数据库（status=草稿），管理员人工校验后发布
    - 增量更新时复用此管线处理新版 PDF
"""
import os
from pathlib import Path
import tempfile
import uuid

from app.core.config import get_settings

settings = get_settings()


class PDFParser:
    """PDF 解析器，逐页提取文本、表格、内嵌图片"""

    def __init__(self, filepath: str):
        import fitz  # PyMuPDF（延迟导入，允许未安装时优雅降级）
        self.filepath = filepath
        self.doc = fitz.open(filepath)
        self.temp_images = []  # 临时图片文件路径列表，关闭时清理

    def parse(self) -> list[dict]:
        """解析 PDF 所有页面，返回每页的结构化数据"""
        pages = []
        for i in range(len(self.doc)):
            page = self.doc[i]
            page_data = {
                "page": i + 1,
                "text": page.get_text("text") or "",
                "tables": self._extract_tables(page),
                "images": self._extract_images(page, i + 1),
            }
            page_data["chunks"] = self._chunk_page(page_data)
            pages.append(page_data)
        return pages

    def _extract_tables(self, page) -> list[dict]:
        """提取页面中的表格（PyMuPDF 版）"""
        tables = []
        # PyMuPDF 1.23+ 支持 find_tables
        try:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for t in tabs.tables:
                    data = t.extract()
                    if data:
                        headers = data[0] if data else []
                        rows = data[1:] if len(data) > 1 else []
                        tables.append({"headers": headers, "rows": rows, "raw": data})
        except Exception:
            pass  # 表格提取失败不阻塞文本提取
        return tables

    def _extract_images(self, page, page_num: int) -> list[dict]:
        """
        提取页面中的内嵌图片

        PyMuPDF 可提取图片的实际字节数据并保存为 PNG 临时文件。
        返回图片信息列表供视觉模型分析。
        """
        images = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            try:
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image.get("image")
                if not image_bytes:
                    continue
                ext = base_image.get("ext", "png")
                # 保存为临时文件供后续视觉分析
                tmp_dir = tempfile.mkdtemp(prefix="pdf_img_")
                img_path = os.path.join(tmp_dir, f"page{page_num}_img{img_index}.{ext}")
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                self.temp_images.append(img_path)

                images.append({
                    "page": page_num,
                    "index": img_index,
                    "path": img_path,
                    "width": base_image.get("width", 0),
                    "height": base_image.get("height", 0),
                    "description": "",  # 待视觉模型填充
                })
            except Exception:
                continue
        return images

    def _chunk_page(self, page_data: dict) -> list[dict]:
        """将一页内容拆分为独立的知识片段"""
        chunks = []
        text = page_data["text"]
        if text:
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                if len(para) > 20:
                    chunks.append({
                        "type": "text",
                        "page": page_data["page"],
                        "content": para,
                    })

        for table in page_data["tables"]:
            table_text = self._table_to_text(table)
            chunks.append({
                "type": "table",
                "page": page_data["page"],
                "content": table_text,
                "structured_data": table,
            })

        for img in page_data["images"]:
            chunks.append({
                "type": "image",
                "page": page_data["page"],
                "image_path": img["path"],
                "width": img["width"],
                "height": img["height"],
                "description": "",  # 待视觉模型填充
            })

        return chunks

    def _table_to_text(self, table: dict) -> str:
        """将表格结构转为可读文本（用于向量嵌入）"""
        lines = []
        if table.get("headers"):
            lines.append(" | ".join(str(h) for h in table["headers"]))
        for row in table.get("rows", []):
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines)

    def get_all_chunks(self, pages: list[dict]) -> list[dict]:
        """聚合所有页面的 chunk，并附加源文件信息"""
        all_chunks = []
        for page in pages:
            for chunk in page.get("chunks", []):
                chunk["source_file"] = os.path.basename(self.filepath)
                all_chunks.append(chunk)
        return all_chunks

    def cleanup(self):
        """清理临时图片文件"""
        for path in self.temp_images:
            try:
                if os.path.exists(path):
                    os.remove(path)
                # 清理空目录
                parent = os.path.dirname(path)
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
            except Exception:
                pass

    def __del__(self):
        try:
            self.doc.close()
            self.cleanup()
        except Exception:
            pass


async def parse_pdf_to_documents(pdf_path: str) -> list[dict]:
    """
    解析 PDF 文件为待入库的文档片段列表

    返回格式与 ChromaVectorStore.add_documents() 兼容：
        [{id, content, metadata: {page, type, source_file, image_path?}}]
    """
    parser = PDFParser(pdf_path)
    pages = parser.parse()
    chunks = parser.get_all_chunks(pages)

    documents = []
    for i, chunk in enumerate(chunks):
        meta = {
            "page": chunk["page"],
            "type": chunk["type"],
            "source_file": chunk.get("source_file", ""),
        }
        # 图片类型附加图片路径信息
        if chunk["type"] == "image" and "image_path" in chunk:
            meta["image_path"] = chunk["image_path"]

        doc = {
            "id": f"{os.path.basename(pdf_path)}_{i}",
            "content": chunk.get("content", "") or chunk.get("description", ""),
            "metadata": meta,
        }
        documents.append(doc)

    return documents
