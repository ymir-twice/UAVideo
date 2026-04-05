# VideoBuddy - 视频理解智能体

**基于工具链增强的多模态视频理解系统**

> 毕业设计项目 - 让文本大模型通过本地工具链理解视觉内容（图片/视频），提供 OpenAI 兼容 API，可接入 VLMEvalKit 测评框架。

## 功能特性

- **OpenAI 兼容 API** - 轻松对接现有框架
- **本地视觉工具** - 无需云端视觉 API
  - 图像描述：vLLM 部署的 Qwen3-VL-4B
  - 音频转写：vLLM 部署的 Qwen3-ASR-1.7B
  - 自适应视频抽帧
- **长短期记忆** - 分层记忆管理
- **ReAct 推理** - 工具增强的复杂视频问答

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    VLMEvalKit / OpenAI 客户端               │
└─────────────────────┬─────────────────────────────────────┘
                      │ OpenAI 兼容 API
┌─────────────────────▼─────────────────────────────────────┐
│                   FastAPI 服务端                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              ReAct 编排器                            │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │  │
│  │  │  短期记忆   │ │  长期记忆   │ │   工具链    │  │  │
│  │  └─────────────┘ └─────────────┘ │             │  │  │
│  │                                  │  ┌─────────┐ │  │  │
│  │                                  │  │ 描述    │ │  │  │
│  │                                  │  │ ASR     │ │  │  │
│  │                                  │  │ 视频    │ │  │  │
│  │                                  │  └─────────┘ │  │  │
│  │                                  └─────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────┬─────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼───────┐           ┌──────▼────────┐
│  vLLM 服务    │           │  豆包 API     │
│  (描述 + ASR) │           │  (语言推理)   │
│  :8802/:8803  │           │               │
└───────────────┘           └───────────────┘
```

## 端口分配

| 服务 | 内网端口 | 公网端口 | 用途 |
|------|---------|---------|------|
| 后端 API | 8800 | 15576 | FastAPI 服务 |
| 前端 Web | 8801 | 15577 | Vite 开发服务器 |
| vLLM Caption | 8802 | 15578 | 图像描述模型 |
| vLLM ASR | 8803 | 15579 | 音频转写模型 |
| vLLM 备用 | 8804 | 15580 | 预留 |
| vLLM 备用 | 8805 | 15581 | 预留 |

**公网访问地址**: http://js3.blockelite.cn

## 快速启动

### 1. 安装依赖

```bash
# 安装 Python 依赖
cd /mnt/data/gk
pip install -r tool_agent/requirements.txt

# 安装 Node.js 依赖（前端）
cd tool_agent/web
npm install
```

### 2. 部署本地视觉模型

使用 vLLM 部署 Qwen3-VL-4B 和 Qwen3-ASR-1.7B：

```bash
# Caption 模型（端口 8802）
vllm serve Qwen3-VL-4B --host 0.0.0.0 --port 8802

# ASR 模型（端口 8803）
vllm serve Qwen3-ASR-1.7B --host 0.0.0.0 --port 8803
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp tool_agent/configs/.env.example tool_agent/configs/.env
# 编辑 .env，填入豆包 API 凭证
```

### 4. 启动服务

```bash
# 启动后端 API（端口 8800）
cd /mnt/data/gk
bash start_server.sh

# 新开终端，启动前端（端口 8801）
cd /mnt/data/gk
bash start_frontend.sh
```

### 5. 访问服务

| 服务 | 地址 |
|------|------|
| 前端界面 | http://js3.blockelite.cn:15577 |
| API 文档 | http://js3.blockelite.cn:15576/docs |
| 健康检查 | http://js3.blockelite.cn:15576/health |

## API 使用

### OpenAI 兼容端点

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-admin",
    base_url="http://js3.blockelite.cn:15576/v1"
)

response = client.chat.completions.create(
    model="tool-agent",
    messages=[
        {"role": "user", "content": "描述这个视频"}
    ]
)
```

### 测试 API

```bash
curl -X POST http://js3.blockelite.cn:15576/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-admin" \
  -d '{
    "model": "tool-agent",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 视频测评

在多个数据集上运行测评：

```bash
# 设置数据目录
export LMUData=/mnt/data/gk/LMUData

# 运行推理（不调用 LLM 评判，节省成本）
PYTHONUSERBASE=/mnt/data/gk/.pyuser \
python3 /mnt/data/gk/VLMEvalKit/run_api.py \
  --data DREAM-1K_8frame moviechat1k_breakpoint_8frame moviechat1k_global_8frame_limit0.01 \
  --model tool-agent \
  --base-url http://js3.blockelite.cn:15576/v1 \
  --key sk-admin \
  --mode infer \
  --api-nproc 16 \
  --timeout 300 \
  --retry 2 \
  --max-samples 50 \
  --work-dir /mnt/data/gk/outputs
```

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务端口 | `8800` |
| `AUTH_TOKEN` | API 认证令牌 | `sk-admin` |
| `CORE_LLM_BASE_URL` | 豆包 API 地址 | - |
| `CORE_LLM_API_KEY` | 豆包 API 密钥 | - |
| `CORE_LLM_MODEL` | 豆包模型名称 | `doubao-seed-1-8-251228` |
| `VLLM_BASE_URL` | vLLM 服务地址 | `http://localhost:8802/v1` |
| `MAX_FRAMES` | 视频最大抽帧数 | `16` |
| `MAX_EVIDENCE_CHARS` | 最大证据字符数 | `12000` |

## 项目结构

```
UAVideo/
├── tool_agent/              # 智能体核心实现
│   ├── server.py           # FastAPI 服务
│   ├── orchestrator.py     # ReAct 编排器
│   ├── memory.py           # 记忆管理
│   ├── session.py         # 会话管理
│   ├── core_llm.py        # 核心 LLM 客户端
│   ├── settings.py        # 配置管理
│   ├── cache.py           # 磁盘缓存
│   ├── tools/             # 工具实现
│   │   ├── caption.py    # 图像描述
│   │   ├── asr.py        # 音频转写
│   │   ├── video.py     # 视频抽帧
│   │   └── vllm_client.py
│   ├── prompts/           # 所有提示词（Markdown）
│   │   ├── caption.md
│   │   ├── asr.md
│   │   ├── video_summary.md
│   │   ├── qa.md
│   │   └── benchmark.md
│   └── web/              # 前端界面
│       ├── src/
│       │   ├── App.vue
│       │   ├── stores/
│       │   └── api/
│       └── public/
├── bench/                  # 测评脚本
├── VLMEvalKit/            # 测评工具包（已修改）
├── LMUData/               # 数据集存储
├── outputs/               # 测评输出
├── pretrained_models/     # 模型配置
│   └── doubao-1.8/
├── start_server.sh         # 后端启动脚本
└── start_frontend.sh       # 前端启动脚本
```

## 记忆系统

### 短期记忆
- 最近帧的滑动窗口（默认 50 帧）
- 按时间自动淘汰（默认 5 分钟）
- 帧级描述和音频转写

### 长期记忆
- 从短期记忆提炼的语义片段
- 基于关键词检索相关片段
- 可配置最大片段数（默认 20）

## 提示词

所有提示词都提取到 `tool_agent/prompts/` 目录下，便于定制：

| 文件 | 用途 |
|------|------|
| `caption.md` | 图像描述提示词 |
| `asr.md` | 音频转写提示词 |
| `video_summary.md` | 视频摘要生成 |
| `qa.md` | 问答任务 |
| `benchmark.md` | 测评任务 |
| `frame_extraction.md` | 帧提取策略 |

## 许可证

MIT License

## 引用

如果您在研究中使用了本项目，请引用：

```bibtex
@misc{uavideo2024,
  title={VideoBuddy: 视频理解智能体},
  author={},
  year={2024},
  url={https://github.com/ymir-twice/UAVideo}
}
```
