"""Ollama 本地 embedding 服务（W1.3 混合检索）

设计定稿（2026-08-12）：向量用 ollama 本地 bge-m3，POST /api/embeddings。
任何失败（不可达/超时/模型缺失）一律返回 None，绝不抛错——
调用方据此走降级路径（参考 TencentDB-Agent-Memory store 的 isDegraded() 设计）。
"""
from __future__ import annotations

from typing import List, Optional

import requests
import structlog

from infrastructure.config import get_config

logger = structlog.get_logger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "bge-m3"


class OllamaEmbeddingService:
    """ollama /api/embeddings 客户端，失败静默降级"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        connect_timeout: float = 3.0,
        read_timeout: float = 30.0,
    ):
        config = get_config()
        self.base_url = (
            base_url
            or config.app.ollama_base_url
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = (
            model
            or config.app.memory_embedding_model
            or DEFAULT_MODEL
        )
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def embed(self, text: str) -> Optional[List[float]]:
        """计算文本 embedding，失败返回 None（降级信号）

        Args:
            text: 输入文本（调用方负责拼接 title+content）

        Returns:
            浮点向量（bge-m3 为 1024 维），失败时 None
        """
        if not text or not text.strip():
            return None
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=(self.connect_timeout, self.read_timeout),
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding")
            if not embedding or not isinstance(embedding, list):
                logger.warning(
                    f"ollama embeddings bad payload: model={self.model} keys={list(data.keys())}"
                )
                return None
            return embedding
        except Exception as e:
            logger.warning(
                f"ollama embeddings unavailable (degraded): {type(e).__name__}: {e}"
            )
            return None
