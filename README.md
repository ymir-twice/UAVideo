# UAVideo

**Tool-Augmented Multimodal Agent for Video Understanding**

> 🎓 **Graduation Thesis Project** - Enables text-only LLMs to understand and process visual content (images/videos) through a local toolchain, with OpenAI-compatible API for VLMEvalKit integration.

## Features

- **OpenAI-Compatible API** - Easy integration with existing frameworks
- **Local Vision Tools** - No cloud vision API required
  - Image captioning via vLLM-deployed Qwen3-VL-4B
  - Audio transcription via vLLM-deployed Qwen3-ASR-1.7B
  - Adaptive video frame extraction
- **Long/Short-Term Memory** - Hierarchical memory management for video understanding
- **ReAct Reasoning** - Tool-augmented reasoning for complex video QA

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    VLMEvalKit / OpenAI Client               │
└─────────────────────┬─────────────────────────────────────┘
                      │ OpenAI-compatible API (:18080)
┌─────────────────────▼─────────────────────────────────────┐
│                   FastAPI Server                            │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              ReAct Orchestrator                      │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │  │
│  │  │  Short-term │ │  Long-term  │ │   Tools     │  │  │
│  │  │   Memory    │ │   Memory    │ │             │  │  │
│  │  └─────────────┘ └─────────────┘ │  ┌─────────┐ │  │  │
│  │                                  │  │ Caption │ │  │  │
│  │                                  │  │   ASR   │ │  │  │
│  │                                  │  │  Video  │ │  │  │
│  │                                  │  └─────────┘ │  │  │
│  │                                  └─────────────┘  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────┬─────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼───────┐           ┌──────▼────────┐
│  vLLM Server  │           │  Doubao API    │
│  (Caption +   │           │  (Language     │
│   ASR)        │           │   Reasoning)   │
│  :8008        │           │                │
└───────────────┘           └───────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd tool_agent
pip install -r requirements.txt
```

### 2. Deploy Local Vision Models

Deploy Qwen3-VL-4B and Qwen3-ASR-1.7B using vLLM:

```bash
# Caption Model (Port 8008)
vllm serve Qwen3-VL-4B --host 0.0.0.0 --port 8008

# ASR Model (Port 8009)
vllm serve Qwen3-ASR-1.7B --host 0.0.0.0 --port 8009
```

### 3. Configure Environment

```bash
cp tool_agent/configs/.env.example tool_agent/configs/.env
# Edit .env with your Doubao API credentials
```

### 4. Start the Server

```bash
bash start_server.sh
```

Or manually:

```bash
cd tool_agent
AUTH_TOKEN=sk-admin PORT=18080 \
CORE_LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3 \
CORE_LLM_API_KEY=your-api-key \
CORE_LLM_MODEL=doubao-seed-1-8-251228 \
python -m tool_agent.server
```

### 5. Test the API

```bash
curl -X POST http://localhost:18080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-admin" \
  -d '{
    "model": "tool-agent",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## API Usage

### OpenAI-Compatible Endpoint

```python
import openai

client = openai.OpenAI(
    api_key="sk-admin",
    base_url="http://localhost:18080/v1"
)

response = client.chat.completions.create(
    model="tool-agent",
    messages=[
        {"role": "user", "content": "Describe this video"}
    ]
)
```

### With Images

```python
import base64

# Encode image
with open("image.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="tool-agent",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": "Describe this image"}
        ]
    }]
)
```

## Benchmarks

Run evaluations on multiple datasets:

```bash
# DREAM-1K (event understanding)
python bench/evaluate.py --model agent --dataset dream1k --max-samples 50

# MMBench-Video (open QA)
python bench/evaluate.py --model agent --dataset mmbench_video --max-samples 50

# MVBench (multiple choice)
python bench/evaluate.py --model agent --dataset mvbench --max-samples 50

# MovieChat-1K (global + breakpoint QA)
python bench/evaluate.py --model agent --dataset moviechat1k --max-samples 50
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `18080` |
| `AUTH_TOKEN` | API auth token | `sk-admin` |
| `CORE_LLM_BASE_URL` | Doubao API URL | - |
| `CORE_LLM_API_KEY` | Doubao API key | - |
| `CORE_LLM_MODEL` | Doubao model name | `doubao-seed-1-8-251228` |
| `VLLM_BASE_URL` | vLLM server URL | `http://localhost:8008/v1` |
| `VLLM_CAPTION_MODEL` | Caption model | `Qwen3-VL-4B` |
| `VLLM_ASR_MODEL` | ASR model | `Qwen3-ASR-1.7B` |
| `MAX_FRAMES` | Max frames per video | `16` |
| `MAX_EVIDENCE_CHARS` | Max evidence chars | `12000` |

## Project Structure

```
UAVideo/
├── tool_agent/              # Main agent implementation
│   ├── server.py           # FastAPI server
│   ├── orchestrator.py     # ReAct orchestrator
│   ├── memory.py          # Memory management
│   ├── session.py          # Session management
│   ├── core_llm.py        # Core LLM client
│   ├── settings.py         # Configuration
│   ├── cache.py            # Disk cache
│   ├── tools/              # Tool implementations
│   │   ├── caption.py     # Image captioning
│   │   ├── asr.py         # Audio transcription
│   │   ├── video.py       # Frame extraction
│   │   └── vllm_client.py # vLLM client
│   └── prompts/            # All prompts (markdown)
│       ├── caption.md
│       ├── asr.md
│       ├── video_summary.md
│       ├── qa.md
│       ├── benchmark.md
│       └── frame_extraction.md
├── bench/                   # Benchmarking scripts
│   ├── evaluate.py         # Unified evaluation
│   ├── test_apis.py        # API tests
│   └── config_loader.py    # Config utilities
├── VLMEvalKit/              # Evaluation toolkit (modified)
├── LMUData/                 # Dataset storage
│   └── datasets/
│       ├── DREAM-1K/
│       ├── MMBench-Video/
│       ├── MovieChat-1K-test/
│       └── MVBench/
├── outputs/                 # Evaluation outputs
├── pretrained_models/        # Model configurations
│   └── doubao-1.8/
└── start_server.sh          # One-click server startup
```

## Memory System

### Short-Term Memory
- Sliding window of recent frames (configurable: 50 frames)
- Auto-pruning by age (default: 5 minutes)
- Frame-level captions and audio transcription

### Long-Term Memory
- Semantic segments extracted from short-term memory
- Keyword-based retrieval for relevant segments
- Configurable max segments (default: 20)

## Tool Chain

### Video Frame Extraction
- Adaptive extraction based on color histogram differences
- Uniform extraction as fallback
- Configurable min/max frames

### Image Captioning
- vLLM-deployed Qwen3-VL-4B
- Base64-encoded images
- Configurable prompts (see `tool_agent/prompts/`)

### ASR (Audio Transcription)
- vLLM-deployed Qwen3-ASR-1.7B
- Audio extracted from video via ffmpeg
- Supports prompt context

## Prompts

All prompts are extracted into `tool_agent/prompts/` for easy customization:

| File | Purpose |
|------|---------|
| `caption.md` | Image captioning prompts |
| `asr.md` | Audio transcription prompts |
| `video_summary.md` | Video summary generation |
| `qa.md` | Question answering |
| `benchmark.md` | Benchmark evaluation |
| `frame_extraction.md` | Frame extraction |

## License

MIT License

## Citation

If you use this project for research, please cite:

```bibtex
@misc{uavideo2024,
  title={UAVideo: Tool-Augmented Multimodal Agent for Video Understanding},
  author={},
  year={2024},
  url={https://github.com/ymir-twice/UAVideo}
}
```
