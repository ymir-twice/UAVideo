# bench

用于复现 VLMEvalKit 对本项目代理服务的 3 个视频数据集推理跑测（第一阶段固定清单）。

## 数据集（固定 3 个）

- `DREAM-1K_8frame`
- `moviechat1k_breakpoint_8frame`
- `moviechat1k_global_8frame_limit0.01`

## 依赖安装（在本环境中）

本工作区使用可写用户目录安装依赖：

```bash
PYTHONUSERBASE=/mnt/data/gk/.pyuser python3 /mnt/data/gk/get-pip.py --user
PYTHONUSERBASE=/mnt/data/gk/.pyuser python3 -m pip install --user -r /mnt/data/gk/tool_agent/requirements.txt
```

## 启动 agent server

```bash
PYTHONUSERBASE=/mnt/data/gk/.pyuser \\
AUTH_TOKEN=sk-admin \\
PORT=18080 \\
CORE_LLM_BASE_URL=<你的核心LLM base_url> \\
CORE_LLM_API_KEY=<你的核心LLM key> \\
CORE_LLM_MODEL=<你的核心LLM model> \\
python3 -m tool_agent.server
```

## 跑 VLMEvalKit（仅推理，省成本）

建议将数据集下载到工作区可写目录：

```bash
export LMUData=/mnt/data/gk/LMUData
```

下载太慢时的常用加速手段（可选）：

```bash
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_TELEMETRY=1
export HF_TOKEN=<可选，若你自己的网络/账号有更高限速>
```

推理跑测（带样本上限）：

```bash
PYTHONUSERBASE=/mnt/data/gk/.pyuser \\
python3 /mnt/data/gk/VLMEvalKit/run_api.py \\
  --data DREAM-1K_8frame moviechat1k_breakpoint_8frame moviechat1k_global_8frame_limit0.01 \\
  --model tool-agent \\
  --base-url http://127.0.0.1:18080/v1 \\
  --key sk-admin \\
  --mode infer \\
  --api-nproc 16 \\
  --timeout 300 \\
  --retry 2 \\
  --max-samples 50 \\
  --work-dir /mnt/data/gk/outputs
```

说明：

- `--max-samples` 是我在 `run_api.py` 增加的成本控制开关（每个数据集取前 N 条）。
- `moviechat1k_*` 的数据仓库体积很大（视频常以压缩包/分片形式存放），因此首次下载时即使 `--max-samples` 很小也可能需要较长时间完成数据准备。
- `DREAM-1K` 的 `eval` 阶段需要 judge LLM，成本高；第一阶段默认只跑 `infer` 产出 prediction 文件。

