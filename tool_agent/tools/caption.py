"""
图像描述工具 - 使用vLLM部署的VLM

支持：
- 本地vLLM部署的Qwen3-VL-4B等VLM模型
- 自动重试和缓存
"""

import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from ..cache import DiskCache


@dataclass
class CaptionEngine:
    """
    图像描述引擎

    支持两种模式：
    1. vLLM模式：使用本地vLLM部署的VLM（默认）
    2. HuggingFace模式：使用HuggingFace的pipeline（备选）
    """
    cache: DiskCache
    model_name: str = "Qwen3-VL-4B"
    vllm_base_url: str = "http://localhost:8008/v1"

    _pipe: Optional[object] = None
    _vllm_client: Optional[object] = None

    def _get_vllm_client(self):
        """获取vLLM客户端"""
        if self._vllm_client is None:
            from .vllm_client import VLLMCaptionClient
            self._vllm_client = VLLMCaptionClient(
                config=None
            )
            # 直接设置属性
            self._vllm_client.config.base_url = self.vllm_base_url
            self._vllm_client.model = self.model_name
        return self._vllm_client

    def caption(self, *, image_bytes: bytes, image: Image.Image) -> str:
        """
        生成图像描述

        Args:
            image_bytes: 图片字节数据
            image: PIL Image对象（可选）

        Returns:
            图像描述文本
        """
        # 检查缓存
        key = self.cache.key_for_bytes(image_bytes, {"tool": "caption", "model": self.model_name})
        cached = self.cache.get_text(key)
        if cached is not None:
            return cached

        # 尝试使用vLLM
        try:
            client = self._get_vllm_client()
            result = client.caption_image(image_bytes)
            if not result.startswith("ERROR:"):
                self.cache.set_text(key, result)
                return result
        except Exception as e:
            pass

        # 备选：使用HuggingFace pipeline
        try:
            result = self._caption_huggingface(image)
            if result:
                self.cache.set_text(key, result)
                return result
        except Exception:
            pass

        return ""

    def _caption_huggingface(self, image: Image.Image) -> str:
        """使用HuggingFace pipeline作为备选"""
        if self._pipe is None:
            from transformers import pipeline
            self._pipe = pipeline("image-to-text", model=self.model_name)

        out = self._pipe(image)
        if isinstance(out, list) and out:
            if isinstance(out[0], dict) and isinstance(out[0].get("generated_text"), str):
                return out[0]["generated_text"].strip()
            else:
                return str(out[0]).strip()
        return ""
