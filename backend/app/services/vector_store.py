"""
向量数据库服务：ChromaDB 集成

封装 ChromaDB 的操作，管理知识片段的向量化存储和语义检索。

支持的 Embedding 提供者（通过 EMBEDDING_PROVIDER 配置切换）：
    1. "api"（推荐）— 千问 DashScope Embedding API (text-embedding-v4)
       优点：无需下载模型，中文效果最佳，已有 API Key 即可使用
       缺点：需要网络，有调用费用
    2. "local"          — 本地 BGE-Small-ZH 模型
       优点：离线可用，免费，CPU 即可运行
       缺点：需下载 ~100MB 模型，中文效果不如千问
    3. "builtin"        — ChromaDB 内置默认模型 (all-MiniLM-L6-v2)
       优点：无需任何配置
       缺点：需下载 79MB ONNX 模型，中文效果最弱

降级链路：api → local → builtin
"""
import os
import time
import threading
from typing import Optional

import httpx
from chromadb import PersistentClient, Documents, EmbeddingFunction, Embeddings
from chromadb.utils import embedding_functions

from app.core.config import get_settings

settings = get_settings()


# ==================== 千问 DashScope Embedding API ====================

class QwenEmbeddingFunction(EmbeddingFunction):
    """
    千问 DashScope Embedding API

    调用阿里云 DashScope 的 text-embedding-v4 模型进行文本向量化。
    返回 1024 维向量，中文语义理解能力优于大多数开源模型。
    API 文档：https://help.aliyun.com/zh/dashscope/developer-reference/text-embedding-api

    费用：text-embedding-v4 约 ¥0.0007/千 tokens，远低于对话模型
    """

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        # DashScope Embedding 端点（与对话 API 不同，需单独构造）
        self.url = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
        self.model = "text-embedding-v4"  # 千问最新 Embedding 模型

    def __call__(self, texts: Documents) -> Embeddings:
        """
        调用 DashScope API 批量向量化文本

        参数：
            texts: 文本列表（ChromaDB 传入，可能是多段文本）
        返回：
            向量列表，每个文本对应一个 1024 维浮点数向量
        """
        embeddings = []
        for text in texts:
            vec = self._embed_single(text)
            embeddings.append(vec)
        return embeddings

    def _embed_single(self, text: str, retry: int = 3) -> list[float]:
        """
        向量化单段文本（带重试，处理网络抖动）
        API 请求格式：POST /v1/embeddings { input, model }
        响应格式：{ data: [{ embedding: [浮点数列表] }] }
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "input": text,
        }

        for attempt in range(retry):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(self.url, json=body, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["data"][0]["embedding"]
            except Exception as e:
                if attempt == retry - 1:
                    # 所有重试均失败，返回零向量（不阻断入库流程）
                    import logging
                    logging.getLogger(__name__).warning(
                        f"DashScope Embedding API 调用失败 (重试{retry}次后): {e}"
                    )
                    # 返回零向量占位（后续可重新索引）
                    return [0.0] * 1024
                time.sleep(1.0 * (attempt + 1))  # 递增退避


# ==================== 自定义嵌入函数工厂 ====================

def _create_embedding_function():
    """
    根据配置选择合适的 Embedding 函数

    优先级：
        EMBEDDING_PROVIDER = "api"   → 千问 DashScope API（推荐）
        EMBEDDING_PROVIDER = "local" → 本地 BGE 模型（离线）
        其他 / 出错                  → ChromaDB 内置默认（兜底）
    """
    provider = settings.EMBEDDING_PROVIDER.lower()

    # 1. 千问 API 模式
    if provider == "api" and settings.QWEN_API_KEY:
        try:
            # 快速连通性检查：用短文本测试 API 是否可达
            test_ef = QwenEmbeddingFunction()
            test_ef._embed_single("测试", retry=1)
            return test_ef
        except Exception:
            # API 不可用，继续尝试下一级
            pass

    # 2. 本地 BGE 模型
    if provider == "local":
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=settings.EMBEDDING_MODEL_NAME,
                device=settings.EMBEDDING_DEVICE,
            )
        except Exception:
            pass

    # 3. ChromaDB 内置默认（兜底）
    return embedding_functions.DefaultEmbeddingFunction()


# ==================== ChromaDB 封装 ====================

class ChromaVectorStore:
    """
    ChromaDB 向量存储封装

    提供：
    - 知识文档批量向量化入库
    - 语义检索（返回 Top-K 最相关内容）
    - 文档更新/删除（与知识条目同步）
    - 多 Embedding 提供者支持（api / local / builtin）
    """

    def __init__(self):
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self._client = PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        # 延迟初始化：不在此处加载模型，避免阻塞启动
        self._ef = None
        self._ef_initialized = False
        self._ef_lock = threading.Lock()

    def _init_embedding(self):
        """
        延迟初始化 Embedding 函数

        首次使用时（入库或检索）才加载模型/测试 API 连通性。
        threading.Lock 确保多线程环境下只初始化一次。
        """
        if self._ef_initialized:
            return

        with self._ef_lock:
            if self._ef_initialized:  # 双重检查锁定
                return
            self._ef = _create_embedding_function()
            self._ef_initialized = True

    def get_or_create_collection(self, name: str = "maintenance_knowledge"):
        """获取或创建向量集合（每个集合使用指定 Embedding 函数）"""
        self._init_embedding()
        return self._client.get_or_create_collection(
            name=name,
            embedding_function=self._ef,
        )

    def add_documents(self, documents: list[dict], collection_name: str = "maintenance_knowledge"):
        """
        批量添加文档到向量库

        参数：
            documents: [{id, content, metadata}]
        返回：
            添加的文档数量
        """
        if not documents:
            return

        collection = self.get_or_create_collection(collection_name)

        ids = []
        contents = []
        metadatas = []
        for doc in documents:
            ids.append(doc["id"])
            contents.append(doc["content"])
            # ChromaDB metadata 只接受 str/int/float/bool，其他类型转字符串
            meta = {}
            for k, v in doc.get("metadata", {}).items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                else:
                    meta[k] = str(v)
            metadatas.append(meta)

        collection.add(ids=ids, documents=contents, metadatas=metadatas)
        return len(ids)

    def search(
        self,
        query: str,
        top_k: int = 5,
        collection_name: str = "maintenance_knowledge",
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        """
        语义检索

        参数：
            query: 查询文本（自然语言描述）
            top_k: 返回数量（默认 5）
            filter_metadata: 元数据过滤（如 {"device_model": "XX发动机"}）

        返回：
            [{id, content, metadata, score}]
            score 范围 0-1，越大越相关
        """
        collection = self.get_or_create_collection(collection_name)

        results = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=filter_metadata if filter_metadata else None,
        )

        items = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - (results["distances"][0][i] if results["distances"] else 0),
                })
        return items

    def delete_by_ids(self, ids: list[str], collection_name: str = "maintenance_knowledge"):
        """按 ID 批量删除（知识条目归档/删除时调用）"""
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=ids)

    def update_by_id(self, doc_id: str, content: str, metadata: dict, collection_name: str = "maintenance_knowledge"):
        """按 ID 更新单条文档（知识条目编辑时调用）"""
        collection = self.get_or_create_collection(collection_name)
        clean_meta = {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                      for k, v in metadata.items()}
        collection.update(ids=[doc_id], documents=[content], metadatas=[clean_meta])


# ========== 全局单例 ==========
vector_store = ChromaVectorStore()
