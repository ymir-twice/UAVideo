"""
ASR音频转写工具 - 使用vLLM部署的ASR模型

通过vLLM部署Qwen3-ASR-1.7B进行语音识别
"""

import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

from ..cache import DiskCache


@dataclass
class ASRResult:
    """ASR识别结果"""
    text: str = ""
    timestamps: List[Tuple[float, float, str]] = field(default_factory=list)

    def get_text_at_time(self, timestamp: float, duration: float = 1.0) -> str:
        """获取指定时间点的音频文本"""
        for start, end, text in self.timestamps:
            if start <= timestamp <= end:
                return text
        return ""

    def merge_to_segments(self, segment_duration: float = 10.0) -> List[Dict[str, Any]]:
        """将音频文本按时间段合并"""
        if not self.timestamps:
            return []

        segments = []
        current_segment = {"start": 0, "end": 0, "texts": []}

        for start, end, text in self.timestamps:
            if current_segment["texts"] and start - current_segment["end"] > 2.0:
                segments.append(current_segment)
                current_segment = {"start": start, "end": end, "texts": [text]}
            else:
                current_segment["end"] = end
                current_segment["texts"].append(text)

        if current_segment["texts"]:
            segments.append(current_segment)

        return [
            {
                "start": s["start"],
                "end": s["end"],
                "text": " ".join(s["texts"])
            }
            for s in segments
        ]


class ASREngine:
    """
    ASR引擎 - 使用vLLM部署的ASR模型

    通过HTTP API调用本地vLLM部署的Qwen3-ASR-1.7B
    """

    def __init__(
        self,
        cache: DiskCache,
        vllm_base_url: str = "http://localhost:8008/v1",
        model_name: str = "Qwen3-ASR-1.7B"
    ):
        self.cache = cache
        self.vllm_base_url = vllm_base_url
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        """获取vLLM ASR客户端"""
        if self._client is None:
            from .vllm_client import VLLMASRClient, VLLMConfig
            config = VLLMConfig(
                base_url=self.vllm_base_url,
                asr_model=self.model_name
            )
            self._client = VLLMASRClient(config)
        return self._client

    def transcribe(self, audio_path: str, prompt: str = "") -> ASRResult:
        """
        转写音频文件

        Args:
            audio_path: 音频文件路径
            prompt: 可选的提示词

        Returns:
            ASRResult对象
        """
        # 检查缓存
        key = self.cache.key_for_file(audio_path, {"tool": "asr", "model": self.model_name})
        cached = self.cache.get_json(key)
        if cached:
            return ASRResult(**cached)

        try:
            client = self._get_client()
            with open(audio_path, 'rb') as f:
                audio_bytes = f.read()

            text, _ = client.transcribe(audio_bytes, prompt=prompt)
            asr_result = ASRResult(text=text, timestamps=[])
            self.cache.set_json(key, asr_result.__dict__)
            return asr_result

        except Exception as e:
            raise RuntimeError(f"ASR转写失败: {str(e)}")

    def transcribe_video(self, video_path: str, prompt: str = "") -> ASRResult:
        """直接从视频提取音频并转写"""
        audio_path = self._extract_audio(video_path)
        try:
            return self.transcribe(audio_path, prompt)
        finally:
            if audio_path and Path(audio_path).exists():
                try:
                    Path(audio_path).unlink()
                except:
                    pass

    def _extract_audio(self, video_path: str) -> str:
        """从视频提取音频"""
        key = self.cache.key_for_file(video_path, {"tool": "extract_audio"})
        cached = self.cache.get_text(key)
        if cached and Path(cached).exists():
            return cached

        temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_audio.close()

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            temp_audio.name
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.cache.set_text(key, temp_audio.name)
            return temp_audio.name
        except subprocess.CalledProcessError:
            return ""
