"""
LLM 大模型适配层

支持从数据库读取激活的模型配置（管理员在后台动态切换），.env 仅作为 fallback。
启动时一次性加载配置到内存，运行时零 DB 访问，彻底避免 SQLite 锁冲突。
"""
from abc import ABC, abstractmethod
import httpx
from app.core.config import get_settings

settings = get_settings()


class ModelAdapter(ABC):
    """大模型适配器抽象基类"""
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str: ...
    @abstractmethod
    async def analyze_image(self, image_url: str, prompt: str) -> str: ...


class DeepSeekAdapter(ModelAdapter):
    """DeepSeek 文本模型适配器"""
    def __init__(self, api_key="", api_base="", model=""):
        self.api_key = api_key or settings.DEEPSEEK_API_KEY
        self.api_base = (api_base or settings.DEEPSEEK_API_BASE).rstrip("/")
        self.model = model or settings.DEEPSEEK_MODEL

    async def _request(self, messages, **kwargs):
        url = f"{self.api_base}/v1/chat/completions"
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": self.model, "messages": messages,
                "temperature": kwargs.get("temperature", 0.3),
                "max_tokens": kwargs.get("max_tokens", 8192)}
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(url, json=body, headers=h); r.raise_for_status()
            return r.json()

    async def chat(self, messages, **kwargs) -> str:
        return (await self._request(messages, **kwargs))["choices"][0]["message"]["content"]

    async def analyze_image(self, image_url: str, prompt: str) -> str:
        raise NotImplementedError("DeepSeek 不支持图片分析")


class QwenVLAdapter(ModelAdapter):
    """千问视觉模型适配器"""
    def __init__(self, api_key="", api_base="", model=""):
        self.api_key = api_key or settings.QWEN_API_KEY
        self.api_base = (api_base or settings.QWEN_API_BASE).rstrip("/")
        self.model = model or settings.QWEN_VL_MODEL

    async def _request(self, messages, **kwargs):
        url = f"{self.api_base}/chat/completions"
        h = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {"model": self.model, "messages": messages,
                "temperature": kwargs.get("temperature", 0.3),
                "max_tokens": kwargs.get("max_tokens", 8192)}
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(url, json=body, headers=h); r.raise_for_status()
            return r.json()

    async def chat(self, messages, **kwargs) -> str:
        return (await self._request(messages, **kwargs))["choices"][0]["message"]["content"]

    async def analyze_image(self, image_url: str, prompt: str) -> str:
        msgs = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": prompt}]}]
        return (await self._request(msgs, temperature=0.3))["choices"][0]["message"]["content"]


class ModelRouter:
    """模型路由器：启动时一次性加载配置，运行时零DB访问"""

    def __init__(self):
        self._deepseek = None
        self._qwen = None
        self._db_cfg = {"text": None, "vision": None, "embedding": None}

    @staticmethod
    def _func_type(name: str) -> str:
        n = (name or "").lower()
        if any(k in n for k in ("embed", "bge", "向量")): return "embedding"
        if any(k in n for k in ("vl", "视觉", "vision")): return "vision"
        return "text"

    def load_configs_sync(self):
        """启动时一次性加载（隔离的 sqlite3 连接，不冲突 SQLAlchemy）"""
        import sqlite3, os, json
        db_url = settings.DATABASE_URL
        if not db_url.startswith("sqlite+aiosqlite:///"): return
        db_path = db_url[len("sqlite+aiosqlite:///"):]
        if not os.path.exists(db_path): return
        try:
            conn = sqlite3.connect(db_path, timeout=3.0)
            for row in conn.execute(
                "SELECT model_name, api_base, api_key, parameters FROM model_configs WHERE is_active=1"
            ):
                name, base, key, pr = row[0] or "", row[1] or "", row[2] or "", row[3]
                if not key: continue
                ft = self._func_type(name)
                if not self._db_cfg.get(ft):
                    self._db_cfg[ft] = {"api_key": key, "api_base": base, "model": name}
            conn.close()
        except Exception:
            pass

    def _cfg(self, ft: str) -> dict:
        return self._db_cfg.get(ft) or {}

    @property
    def deepseek(self):
        if not self._deepseek:
            self._deepseek = DeepSeekAdapter(**self._cfg("text"))
        return self._deepseek

    @property
    def qwen(self):
        if not self._qwen:
            self._qwen = QwenVLAdapter(**self._cfg("vision"))
        return self._qwen

    def get_embedding_config(self) -> dict:
        return self._cfg("embedding")

    async def chat(self, messages, has_image=False, **kwargs) -> str:
        return await (self.qwen if has_image else self.deepseek).chat(messages, **kwargs)

    async def analyze_image(self, image_url: str, prompt: str) -> str:
        return await self.qwen.analyze_image(image_url, prompt)

    def invalidate_cache(self):
        """管理员后台修改配置后调用"""
        self._db_cfg = {"text": None, "vision": None, "embedding": None}
        self._deepseek = None; self._qwen = None
        self.load_configs_sync()


model_router = ModelRouter()
