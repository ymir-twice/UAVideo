import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return default
    return int(v)


@dataclass(frozen=True)
class Settings:
    # =============== 服务器配置 ===============
    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 18080)
    auth_token: str = os.environ.get("AUTH_TOKEN", "sk-admin")

    # =============== 核心LLM (豆包 - 仅用于语言推理) ===============
    core_llm_base_url: str = os.environ.get("CORE_LLM_BASE_URL", "").rstrip("/")
    core_llm_api_key: str = os.environ.get("CORE_LLM_API_KEY", "")
    core_llm_model: str = os.environ.get("CORE_LLM_MODEL", "")
    core_llm_timeout: int = _env_int("CORE_LLM_TIMEOUT", 180)

    # =============== 本地vLLM配置 (用于工具能力) ===============
    # vLLM服务地址 - 部署Qwen3-VL-4B和Qwen3-ASR-1.7B后填写
    vllm_base_url: str = os.environ.get("VLLM_BASE_URL", "http://localhost:8008/v1")
    vllm_api_key: str = os.environ.get("VLLM_API_KEY", "EMPTY")
    vllm_timeout: int = _env_int("VLLM_TIMEOUT", 300)

    # vLLM模型名称
    vllm_caption_model: str = os.environ.get("VLLM_CAPTION_MODEL", "Qwen3-VL-4B")
    vllm_asr_model: str = os.environ.get("VLLM_ASR_MODEL", "Qwen3-ASR-1.7B")

    # =============== 缓存和存储 ===============
    cache_dir: str = os.environ.get("CACHE_DIR", "/mnt/data/gk/.cache/tool_agent")
    session_storage_dir: str = os.environ.get("SESSION_STORAGE_DIR", "/mnt/data/gk/.cache/tool_agent/sessions")

    # =============== 帧提取配置 ===============
    max_frames: int = _env_int("MAX_FRAMES", 16)
    adaptive_threshold: float = 0.3  # 自适应抽帧变化阈值

    # =============== Evidence聚合配置 ===============
    max_evidence_chars: int = _env_int("MAX_EVIDENCE_CHARS", 12000)

    # =============== 工具开关 ===============
    caption_enabled: bool = _env_bool("CAPTION_ENABLED", True)
    asr_enabled: bool = _env_bool("ASR_ENABLED", True)

    # =============== 记忆配置 ===============
    short_term_window_size: int = _env_int("SHORT_TERM_WINDOW_SIZE", 50)
    short_term_max_age: int = _env_int("SHORT_TERM_MAX_AGE", 300)
    long_term_max_segments: int = _env_int("LONG_TERM_MAX_SEGMENTS", 20)

    # =============== 向后兼容 ===============
    @staticmethod
    def with_doubao_fallback() -> "Settings":
        """如果核心LLM未配置，使用豆包作为后备"""
        s = Settings()
        if s.core_llm_base_url and s.core_llm_api_key and s.core_llm_model:
            return s
        base = os.environ.get("DOUBAO_BASE_URL", "").rstrip("/")
        key = os.environ.get("DOUBAO_API_KEY", "")
        model = os.environ.get("DOUBAO_MODEL", "")
        if base and key and model:
            os.environ.setdefault("CORE_LLM_BASE_URL", base)
            os.environ.setdefault("CORE_LLM_API_KEY", key)
            os.environ.setdefault("CORE_LLM_MODEL", model)
        return Settings()
