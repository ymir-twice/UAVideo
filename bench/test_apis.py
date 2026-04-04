#!/usr/bin/env python3
"""
API测试脚本 - 测试豆包、vLLM和本地智能体API

同时测试：
1. 豆包API (线上)
2. 本地vLLM服务 (Caption)
3. 本地vLLM服务 (ASR)
4. 本地智能体API (完整pipeline)
"""

import os
import sys
import tempfile
from pathlib import Path

# 加载配置
from config_loader import load_config, load_agent_config

# 加载豆包配置
load_config()


def test_doubao():
    """测试豆包API"""
    print()
    print("=" * 60)
    print("测试1: 豆包API (线上 - 语言推理)")
    print("=" * 60)

    import json
    import time
    import requests

    BASE_URL = os.environ.get('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
    API_KEY = os.environ.get('DOUBAO_API_KEY', '')
    MODEL = os.environ.get('DOUBAO_MODEL', 'doubao-seed-1-8-251228')

    print(f"URL: {BASE_URL}")
    print(f"Model: {MODEL}")

    messages = [
        {"role": "system", "content": "你是AI助手。"},
        {"role": "user", "content": "你好，1+1等于几？"}
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 100
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    start = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=30
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✓ 成功 ({elapsed:.2f}s)")
            print(f"  回答: {content[:100]}")
            return True
        else:
            print(f"✗ 失败: HTTP {response.status_code}")
            print(response.text[:200])
            return False

    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        return False


def test_vllm_caption():
    """测试vLLM Caption"""
    print()
    print("=" * 60)
    print("测试2: vLLM Caption (本地 - 图像描述)")
    print("=" * 60)

    import json
    import time
    import base64
    import requests
    from io import BytesIO
    from PIL import Image

    VLLM_BASE_URL = os.environ.get('VLLM_BASE_URL', 'http://localhost:8008/v1')
    VLLM_API_KEY = os.environ.get('VLLM_API_KEY', 'EMPTY')
    CAPTION_MODEL = os.environ.get('VLLM_CAPTION_MODEL', 'Qwen3-VL-4B')

    print(f"URL: {VLLM_BASE_URL}")
    print(f"Model: {CAPTION_MODEL}")

    # 检查连接
    try:
        resp = requests.get(
            f"{VLLM_BASE_URL}/models",
            headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
            timeout=5
        )
        if resp.status_code != 200:
            print(f"✗ 服务返回: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ 无法连接vLLM服务: {str(e)}")
        print()
        print("提示: 请先启动vLLM服务")
        print(f"  vllm serve {CAPTION_MODEL} --host 0.0.0.0 --port 8008")
        return False

    # 创建测试图片
    img = Image.new('RGB', (100, 100), color=(100, 150, 200))
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    b64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                {"type": "text", "text": "描述这张图片"}
            ]
        }
    ]

    payload = {
        "model": CAPTION_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 128
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VLLM_API_KEY}"
    }

    start = time.time()

    try:
        response = requests.post(
            f"{VLLM_BASE_URL}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✓ 成功 ({elapsed:.2f}s)")
            print(f"  Caption: {content[:100]}")
            return True
        else:
            print(f"✗ 失败: HTTP {response.status_code}")
            print(response.text[:200])
            return False

    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        return False


def test_vllm_asr():
    """测试vLLM ASR"""
    print()
    print("=" * 60)
    print("测试3: vLLM ASR (本地 - 语音识别)")
    print("=" * 60)

    import json
    import time
    import base64
    import subprocess
    import requests

    VLLM_BASE_URL = os.environ.get('VLLM_ASR_BASE_URL', 'http://localhost:8009/v1')
    VLLM_API_KEY = os.environ.get('VLLM_API_KEY', 'EMPTY')
    ASR_MODEL = os.environ.get('VLLM_ASR_MODEL', 'Qwen3-ASR-1.7B')

    print(f"URL: {VLLM_BASE_URL}")
    print(f"Model: {ASR_MODEL}")

    # 检查连接
    try:
        resp = requests.get(
            f"{VLLM_BASE_URL}/models",
            headers={"Authorization": f"Bearer {VLLM_API_KEY}"},
            timeout=5
        )
        if resp.status_code != 200:
            print(f"✗ 服务返回: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ 无法连接vLLM服务: {str(e)}")
        print()
        print("提示: 请先启动vLLM ASR服务")
        print(f"  vllm serve Qwen/Qwen3-ASR-1.7B --host 0.0.0.0 --port 8009")
        return False

    # 创建测试音频 (使用ffmpeg生成1秒的测试音调)
    print("生成测试音频...")
    temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_audio.close()

    try:
        # 生成一个简单的测试音频 (1秒的440Hz正弦波)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ar", "16000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            temp_audio.name
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"✓ 测试音频已生成: {temp_audio.name}")
    except Exception as e:
        print(f"✗ 生成测试音频失败: {e}")
        print("提示: 需要ffmpeg支持")
        return False

    # 读取音频并转为base64
    with open(temp_audio.name, 'rb') as f:
        audio_data = f.read()
    b64_audio = base64.b64encode(audio_data).decode('utf-8')

    # 构建ASR消息 (Qwen3-ASR格式 - 使用audio_url类型)
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "audio_url",
                    "audio_url": {
                        "url": f"data:audio/wav;base64,{b64_audio}"
                    }
                },
                {
                    "type": "text",
                    "text": "请转写这段音频的内容。"
                }
            ]
        }
    ]

    payload = {
        "model": ASR_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 256
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VLLM_API_KEY}"
    }

    start = time.time()

    try:
        response = requests.post(
            f"{VLLM_BASE_URL}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )
        elapsed = time.time() - start

        # 清理临时文件
        try:
            os.unlink(temp_audio.name)
        except:
            pass

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✓ 成功 ({elapsed:.2f}s)")
            print(f"  ASR结果: {content[:100]}")
            return True
        else:
            print(f"✗ 失败: HTTP {response.status_code}")
            print(response.text[:300])
            return False

    except Exception as e:
        # 清理临时文件
        try:
            os.unlink(temp_audio.name)
        except:
            pass
        print(f"✗ 失败: {str(e)}")
        return False


def test_agent_api():
    """测试本地智能体API"""
    print()
    print("=" * 60)
    print("测试4: 本地智能体API (完整pipeline)")
    print("=" * 60)

    import json
    import time
    import base64
    import requests
    from io import BytesIO
    from PIL import Image

    AGENT_BASE_URL = os.environ.get('AGENT_BASE_URL', 'http://localhost:18080')
    AUTH_TOKEN = os.environ.get('AUTH_TOKEN', 'sk-admin')

    print(f"URL: {AGENT_BASE_URL}")
    print(f"Auth Token: {AUTH_TOKEN[:10]}...")

    # 检查健康状态
    try:
        resp = requests.get(
            f"{AGENT_BASE_URL}/health",
            timeout=5
        )
        if resp.status_code != 200:
            print(f"✗ 服务返回: HTTP {resp.status_code}")
            return False
        print(f"✓ 服务健康")
    except Exception as e:
        print(f"✗ 无法连接智能体服务: {str(e)}")
        print()
        print("提示: 请先启动智能体服务")
        print(f"  bash /mnt/data/gk/start_server.sh")
        return False

    # 创建测试图片
    img = Image.new('RGB', (100, 100), color=(100, 150, 200))
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    b64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                {"type": "text", "text": "描述这张图片"}
            ]
        }
    ]

    payload = {
        "model": "tool-agent",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 256
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    start = time.time()

    try:
        response = requests.post(
            f"{AGENT_BASE_URL}/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=120
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✓ 成功 ({elapsed:.2f}s)")
            print(f"  回答: {content[:200]}")
            return True
        else:
            print(f"✗ 失败: HTTP {response.status_code}")
            print(response.text[:200])
            return False

    except Exception as e:
        print(f"✗ 失败: {str(e)}")
        return False


def main():
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "API测试 - 豆包 & vLLM & Agent" + " " * 8 + "║")
    print("╚" + "═" * 58 + "╝")

    results = []

    # 测试豆包
    doubao_ok = test_doubao()
    results.append(("豆包API", doubao_ok))

    # 测试vLLM Caption
    caption_ok = test_vllm_caption()
    results.append(("vLLM Caption", caption_ok))

    # 测试vLLM ASR
    asr_ok = test_vllm_asr()
    results.append(("vLLM ASR", asr_ok))

    # 测试本地智能体API
    agent_ok = test_agent_api()
    results.append(("本地智能体API", agent_ok))

    # 汇总
    print()
    print("=" * 60)
    print("测试汇总")
    print("=" * 60)

    for name, ok in results:
        status = "✓ 正常" if ok else "✗ 异常"
        print(f"  {name}: {status}")

    print()
    all_ok = all(r[1] for r in results)
    if all_ok:
        print("✓ 所有服务正常！可以开始评测。")
        print()
        print("评测命令:")
        print("  # 测试本地agent")
        print("  python bench/evaluate.py --model agent --dataset dream1k --max-samples 10")
        print()
        print("  # 测试豆包直接API")
        print("  python bench/evaluate.py --model doubao --dataset dream1k --max-samples 10")
    elif results[0][1]:  # 豆包正常
        print("⚠ 部分服务异常:")
        if not results[1][1]:
            print("  - vLLM Caption未启动")
        if not results[2][1]:
            print("  - vLLM ASR未启动")
        if not results[3][1]:
            print("  - 本地智能体API未启动")
        print()
        print("豆包可用，仍可启动评测（使用豆包API）:")
        print("  python bench/evaluate.py --model doubao --dataset dream1k --max-samples 10")
    else:
        print("✗ 豆包API异常，请检查网络和配置")

    print()
    return 0 if results[0][1] else 1


if __name__ == "__main__":
    sys.exit(main())
