"""
vLLM 服务客户端

用于调用本地vLLM部署的模型：
- Qwen3-VL-4B (图像caption)
- Qwen3-ASR-1.7B (语音识别)
"""

import json
import base64
import requests
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class VLLMConfig:
    """vLLM服务配置"""
    base_url: str = "http://localhost:8008/v1"
    api_key: str = "EMPTY"  # vLLM默认不需要key
    timeout: int = 300

    # 模型名称
    caption_model: str = "Qwen3-VL-4B"
    asr_model: str = "Qwen3-ASR-1.7B"


class VLLMClient:
    """vLLM API客户端"""

    def __init__(self, config: Optional[VLLMConfig] = None):
        self.config = config or VLLMConfig()

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发送POST请求"""
        url = f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        response = requests.post(
            url,
            headers=headers,
            data=json.dumps(payload),
            timeout=self.config.timeout
        )
        response.raise_for_status()
        return response.json()

    def chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        """通用chat接口"""
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        result = self._post("chat/completions", payload)
        return result["choices"][0]["message"]["content"]

    def generate(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048
    ) -> str:
        """通用generate接口"""
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        result = self._post("completions", payload)
        return result["choices"][0]["text"]


class VLLMCaptionClient(VLLMClient):
    """使用vLLM部署的VLM做图像描述"""

    def __init__(self, config: Optional[VLLMConfig] = None):
        super().__init__(config)
        if config and config.caption_model:
            self.model = config.caption_model
        else:
            self.model = "Qwen3-VL-4B"

    def caption_image(
        self,
        image_bytes: bytes,
        prompt: str = "描述这张图片的内容，用简洁的语言说明画面中有什么，以及发生了什么。",
        timeout: int = 60
    ) -> str:
        """
        对单张图片生成描述

        Args:
            image_bytes: 图片字节数据
            prompt: 提示词
            timeout: 超时时间

        Returns:
            图片描述文本
        """
        # 将图片转为base64
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 512
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=timeout
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            return "ERROR: Caption timeout"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def caption_images(
        self,
        image_bytes_list: List[bytes],
        prompt: str = "依次描述这些图片的内容，用简洁的语言说明每张画面中有什么。"
    ) -> List[str]:
        """
        对多张图片生成描述

        Args:
            image_bytes_list: 图片字节数据列表
            prompt: 提示词

        Returns:
            图片描述列表
        """
        if not image_bytes_list:
            return []

        # 构建消息 - 多图模式
        content = []
        for img_bytes in image_bytes_list:
            b64_image = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image}"
                }
            })

        content.append({
            "type": "text",
            "text": prompt
        })

        messages = [{"role": "user", "content": content}]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1024
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()

            # 尝试解析为多行描述
            lines = [line.strip() for line in content.split("\n") if line.strip()]
            return lines if lines else [content]

        except Exception as e:
            return [f"ERROR: {str(e)}"]


class VLLMASRClient(VLLMClient):
    """使用vLLM部署的ASR模型做语音识别"""

    def __init__(self, config: Optional[VLLMConfig] = None):
        super().__init__(config)
        if config and config.asr_model:
            self.model = config.asr_model
        else:
            self.model = "Qwen3-ASR-1.7B"

    def transcribe(
        self,
        audio_bytes: bytes,
        prompt: str = "",
        language: str = "zh",
        timestamp: bool = True
    ) -> Tuple[str, List[Tuple[float, float, str]]]:
        """
        语音转文字

        Args:
            audio_bytes: 音频字节数据 (wav/pcm格式)
            prompt: 可选的提示词
            language: 语言代码
            timestamp: 是否返回时间戳

        Returns:
            (转写文本, 时间戳列表[(start, end, text)])
        """
        # 将音频转为base64
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

        # Qwen3-ASR的消息格式
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio",
                        "audio": {
                            "url": f"data:audio/wav;base64,{b64_audio}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt or "请转写这段音频的内容。"
                    }
                ]
            }
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 2048
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            text = result["choices"][0]["message"]["content"].strip()

            # 注意：vLLM部署的ASR可能不返回时间戳，这里简化处理
            # 如果需要时间戳，需要使用专门的ASR服务（如FunASR）
            return text, []

        except Exception as e:
            return f"ERROR: {str(e)}", []


def create_vllm_clients(
    base_url: str = "http://localhost:8008/v1",
    caption_model: str = "Qwen3-VL-4B",
    asr_model: str = "Qwen3-ASR-1.7B"
) -> Tuple[VLLMCaptionClient, VLLMASRClient]:
    """创建vLLM客户端"""
    config = VLLMConfig(
        base_url=base_url,
        caption_model=caption_model,
        asr_model=asr_model
    )
    return VLLMCaptionClient(config), VLLMASRClient(config)
