#!/usr/bin/env python3
"""
配置文件加载工具
"""

import os
from pathlib import Path


def load_config():
    """加载豆包配置文件到环境变量"""
    project_dir = Path("/mnt/data/gk")

    # 豆包配置
    doubao_config = project_dir / "pretrained_models" / "doubao-1.8"
    if doubao_config.exists():
        with open(doubao_config, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

    return {
        'doubao_base_url': os.environ.get('DOUBAO_BASE_URL', ''),
        'doubao_api_key': os.environ.get('DOUBAO_API_KEY', ''),
        'doubao_model': os.environ.get('DOUBAO_MODEL', ''),
    }


def load_agent_config():
    """加载智能体配置到环境变量"""
    project_dir = Path("/mnt/data/gk")

    # 智能体配置文件
    agent_config = project_dir / "tool_agent" / "configs" / ".env"
    if agent_config.exists():
        with open(agent_config, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

    # 豆包配置 (备选)
    doubao_config = project_dir / "pretrained_models" / "doubao-1.8"
    if doubao_config.exists():
        with open(doubao_config, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:  # 不覆盖已存在的配置
                        os.environ[key] = value

    return {
        'core_llm_base_url': os.environ.get('CORE_LLM_BASE_URL', ''),
        'core_llm_api_key': os.environ.get('CORE_LLM_API_KEY', ''),
        'core_llm_model': os.environ.get('CORE_LLM_MODEL', ''),
        'vllm_base_url': os.environ.get('VLLM_BASE_URL', ''),
        'vllm_api_key': os.environ.get('VLLM_API_KEY', ''),
    }


if __name__ == "__main__":
    config = load_config()
    print("豆包配置:")
    for key, value in config.items():
        if key.endswith('_key'):
            value = value[:10] + "..." if value else ""
        print(f"  {key}: {value}")
