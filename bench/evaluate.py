#!/usr/bin/env python3
"""
统一评测框架 - 支持多模型多数据集评测

支持评测的模型类型:
- agent: 本地视频理解智能体 (OpenAI兼容API)
- doubao: 豆包1.8直接API调用
- openai: OpenAI兼容API

用法:
  # 测试本地agent (默认)
  python bench/evaluate.py --model agent --dataset dream1k --max-samples 10

  # 测试豆包直接API
  python bench/evaluate.py --model doubao --dataset dream1k --max-samples 10

  # 测试其他OpenAI兼容API
  python bench/evaluate.py --model openai --base-url http://host:port/v1 \
       --api-key xxx --model-name gpt-4v --dataset dream1k --max-samples 10

数据集:
- dream1k: DREAM-1K 视频理解数据集 (事件recall/precision)
- mmbench_video: MMBench-Video 数据集 (开放问答)
- moviechat1k: MovieChat-1K 数据集 (全局+断点问答)
- mvbench: MVBench 数据集 (多选题)
"""

import sys
import os
import json
import time
import base64
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import argparse
import statistics

# Project paths
PROJECT_DIR = Path("/mnt/data/gk")
sys.path.insert(0, str(PROJECT_DIR))

# Import project config loader
from bench.config_loader import load_config


@dataclass
class ModelConfig:
    """模型配置"""
    model_type: str  # agent, doubao, openai
    base_url: str = ""
    api_key: str = ""
    model_name: str = ""
    auth_token: str = ""


@dataclass
class EvalStats:
    """评测统计信息"""
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration: float = 0.0
    request_durations: List[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def add_request(self, input_tokens: int, output_tokens: int, duration: float):
        with self.lock:
            self.total_requests += 1
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_duration += duration
            self.request_durations.append(duration)


class BaseAPIClient:
    """API客户端基类"""

    def __init__(self, config: ModelConfig, stats: EvalStats):
        self.config = config
        self.stats = stats

    def chat(self, messages: List[Dict], max_tokens: int = 2048, temperature: float = 0.0) -> Tuple[str, Optional[Dict]]:
        """发送chat请求，返回(content, usage_info)"""
        raise NotImplementedError


class AgentAPIClient(BaseAPIClient):
    """本地智能体API客户端"""

    def __init__(self, config: ModelConfig, stats: EvalStats):
        super().__init__(config, stats)
        import requests
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.auth_token}"})

    def chat(self, messages: List[Dict], max_tokens: int = 2048, temperature: float = 0.0) -> Tuple[str, Optional[Dict]]:
        """通过智能体API发送请求"""
        import requests

        payload = {
            "model": self.config.model_name or "tool-agent",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                timeout=300
            )
            duration = time.time() - start_time

            if response.status_code == 200:
                resp_data = response.json()
                content = resp_data['choices'][0]['message']['content']
                usage = resp_data.get('usage', {})
                self.stats.add_request(
                    usage.get('prompt_tokens', 0),
                    usage.get('completion_tokens', 0),
                    duration
                )
                return content, {'duration': duration, **usage}
            else:
                return f"ERROR: {response.status_code} - {response.text[:200]}", None
        except Exception as e:
            duration = time.time() - start_time
            return f"ERROR: {str(e)}", None


class DoubaoAPIClient(BaseAPIClient):
    """豆包API客户端"""

    def __init__(self, config: ModelConfig, stats: EvalStats):
        super().__init__(config, stats)
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        })

    def chat(self, messages: List[Dict], max_tokens: int = 2048, temperature: float = 0.0) -> Tuple[str, Optional[Dict]]:
        """调用豆包API"""
        import requests

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.config.base_url}/chat/completions",
                data=json.dumps(payload),
                timeout=300
            )
            duration = time.time() - start_time

            if response.status_code == 200:
                resp_data = response.json()
                content = resp_data['choices'][0]['message']['content']
                usage = resp_data.get('usage', {})
                self.stats.add_request(
                    usage.get('prompt_tokens', 0),
                    usage.get('completion_tokens', 0),
                    duration
                )
                return content, {'duration': duration, **usage}
            else:
                return f"ERROR: {response.status_code} - {response.text[:200]}", None
        except Exception as e:
            duration = time.time() - start_time
            return f"ERROR: {str(e)}", None


class OpenAIAPIClient(BaseAPIClient):
    """通用OpenAI兼容API客户端"""

    def __init__(self, config: ModelConfig, stats: EvalStats):
        super().__init__(config, stats)
        import requests
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        })

    def chat(self, messages: List[Dict], max_tokens: int = 2048, temperature: float = 0.0) -> Tuple[str, Optional[Dict]]:
        """调用OpenAI兼容API"""
        import requests

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                timeout=300
            )
            duration = time.time() - start_time

            if response.status_code == 200:
                resp_data = response.json()
                content = resp_data['choices'][0]['message']['content']
                usage = resp_data.get('usage', {})
                self.stats.add_request(
                    usage.get('prompt_tokens', 0),
                    usage.get('completion_tokens', 0),
                    duration
                )
                return content, {'duration': duration, **usage}
            else:
                return f"ERROR: {response.status_code} - {response.text[:200]}", None
        except Exception as e:
            duration = time.time() - start_time
            return f"ERROR: {str(e)}", None


def create_api_client(config: ModelConfig, stats: EvalStats) -> BaseAPIClient:
    """根据配置创建API客户端"""
    if config.model_type == "agent":
        return AgentAPIClient(config, stats)
    elif config.model_type == "doubao":
        return DoubaoAPIClient(config, stats)
    elif config.model_type == "openai":
        return OpenAIAPIClient(config, stats)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")


def extract_frames(video_path: str, n_frames: int = 16) -> Tuple[List[str], Path]:
    """用ffmpeg均匀抽取视频帧"""
    try:
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "format=duration", "-of", "json", video_path]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        data = json.loads(result.stdout.decode("utf-8"))
        duration = float(data["format"]["duration"])
    except:
        duration = 10.0

    temp_dir = Path("/tmp/video_frames") / f"{os.getpid()}_{int(time.time()*1000)}_{threading.get_ident()}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    fps = max(0.1, n_frames / duration)
    out_pattern = str(temp_dir / "frame_%04d.jpg")
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}", "-q:v", "2", out_pattern]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except:
        pass

    frames = sorted(temp_dir.glob("frame_*.jpg"))[:n_frames]

    if len(frames) < n_frames:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={n_frames/duration}", "-q:v", "2", out_pattern]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass
        frames = sorted(temp_dir.glob("frame_*.jpg"))[:n_frames]

    return [str(f) for f in frames], temp_dir


def frame_to_base64(image_path: str) -> str:
    """将图片转为base64的data URL"""
    with open(image_path, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode('utf-8')
    return f"data:image/jpeg;base64,{b64}"


def generate_video_description(api_client: BaseAPIClient, video_path: str, n_frames: int = 16,
                                prompt: str = "请详细描述这个视频的内容，包括所有动作、事件和运动。用中文描述。") -> Tuple[str, Optional[Dict]]:
    """用多模态模型生成视频描述（n帧base64）"""
    frames, temp_dir = extract_frames(video_path, n_frames=n_frames)

    content = []
    for frame_path in frames:
        b64_url = frame_to_base64(frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": b64_url}
        })

    content.append({
        "type": "text",
        "text": prompt
    })

    messages = [{"role": "user", "content": content}]
    shutil.rmtree(temp_dir, ignore_errors=True)

    for retry in range(3):
        result, usage = api_client.chat(messages, max_tokens=1024, temperature=0.0)
        if not result.startswith("ERROR"):
            return result, usage
        time.sleep(2)

    return "ERROR: Failed to generate description", None


def extract_events_from_prediction(api_client: BaseAPIClient, description: str) -> Tuple[List[str], Optional[Dict]]:
    """从预测描述中提取事件"""
    prompt = f"""Bellow is a description of a video clip:
Video Description: {description}

Extract at most 10 key events from the above video description paragraph. Requirements:
- An event must include an action, motion or movement (NOT STATIC INFORMATION). DON'T repeat same events.
- Every event is represented by a brief sentence within 10 words, with a subject, a predicate and optionally an object, avoid unnecessary appearance descriptions.
- Every event must be atomic, meaning that it cannot be further split into multiple events.
- Scene cuts and camera motions are NOT events.
- Substitute pronouns by the nouns they refer to.

Please generate the response in the form of a JSON dictionary with keys "events". The value of "events" is a List(str), of which each item is an event.
DO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only provide the JSON."""

    messages = [{"role": "user", "content": prompt}]

    for retry in range(5):
        result, usage = api_client.chat(messages, max_tokens=1024, temperature=0.0)
        if result.startswith("ERROR"):
            time.sleep(2)
            continue

        result = result.strip()
        if result.startswith("```json"):
            result = result.replace("```json", "").replace("```", "").strip()
        elif result.startswith("```python"):
            result = result.replace("```python", "").replace("```", "").strip()

        try:
            data = json.loads(result)
            if 'events' in data and isinstance(data['events'], list):
                return data['events'], usage
        except:
            time.sleep(2)
            continue

    return [], None


def evaluate_entailment(api_client: BaseAPIClient, events: List[str], description: str) -> Tuple[float, List[Dict], Optional[Dict]]:
    """判断事件与描述之间的蕴涵关系"""
    prompt = f"""Given a video description and a list of events. For each event, classify the relationship between the video description and the event into three classes: entailment, neutral, contradiction.
- "entailment" means that the video description entails the event.
- "contradiction" means that some detail in the video description contradicts with the event.
- "neutral" means that the relationship is neither "entailment" or "contradiction".

Video Description:
{description}

Events: {events}

Output a JSON formed as:
{{
  "events": [
    {{"event": "copy an event here", "relationship": "put class name here", "reason": "give your reason here"}},
    ...
  ]
}}

DO NOT PROVIDE ANY OTHER OUTPUT TEXT OR EXPLANATION. Only output the JSON."""

    messages = [{"role": "user", "content": prompt}]

    for retry in range(5):
        result, usage = api_client.chat(messages, max_tokens=2048, temperature=0.0)
        if result.startswith("ERROR"):
            time.sleep(2)
            continue

        result = result.strip()
        if result.startswith("```json"):
            result = result.replace("```json", "").replace("```", "").strip()
        if not result.startswith('{'):
            result = '{' + result
        if not result.endswith('}'):
            result = result + '}'

        try:
            data = json.loads(result)
            if 'events' in data and isinstance(data['events'], list):
                entail_count = sum(1 for e in data['events'] if e.get('relationship', '').lower().strip() == 'entailment')
                score = entail_count / len(data['events']) if data['events'] else 0
                return score, data['events'], usage
        except:
            time.sleep(2)
            continue

    return 0, [], None


def process_dream1k_sample(item: Dict, api_client: BaseAPIClient, n_frames: int, stats: EvalStats) -> Dict:
    """处理单个DREAM-1K样本"""
    idx = item['idx']
    video_path = PROJECT_DIR / "LMUData" / "datasets" / "dream1k" / "video" / f"{idx}.mp4"

    gt_description = item.get('description', '')
    gt_events = item.get('events', [])

    sample_stats = {
        'total_duration': 0.0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'api_calls': 0,
    }

    # 生成预测描述
    pred_description, usage = generate_video_description(api_client, str(video_path), n_frames=n_frames)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # 从预测描述中提取事件
    pred_events, usage = extract_events_from_prediction(api_client, pred_description)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # 计算Recall
    recall_score = 0
    if gt_events:
        recall_score, _, usage = evaluate_entailment(api_client, gt_events, pred_description)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1

    # 计算Precision
    precision_score = 0
    if pred_events:
        precision_score, _, usage = evaluate_entailment(api_client, pred_events, gt_description)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1

    return {
        'idx': idx,
        'gt_description': gt_description,
        'gt_events': gt_events,
        'pred_description': pred_description,
        'pred_events': pred_events,
        'recall': recall_score,
        'precision': precision_score,
        'sample_stats': sample_stats,
    }


def process_moviechat_sample(item: Dict, api_client: BaseAPIClient, n_frames: int, stats: EvalStats) -> Dict:
    """处理单个MovieChat-1K样本"""
    # MovieChat-1K数据结构可能与DREAM-1K不同，这里做兼容处理
    idx = item.get('video_id', item.get('idx', 0))
    video_path = PROJECT_DIR / "LMUData" / "datasets" / "moviechat1k" / "video" / f"{idx}.mp4"

    gt_description = item.get('description', item.get('gt_description', ''))
    gt_events = item.get('events', item.get('gt_events', []))

    sample_stats = {
        'total_duration': 0.0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'api_calls': 0,
    }

    # 生成预测描述
    pred_description, usage = generate_video_description(api_client, str(video_path), n_frames=n_frames)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # 从预测描述中提取事件
    pred_events, usage = extract_events_from_prediction(api_client, pred_description)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # 计算Recall
    recall_score = 0
    if gt_events:
        recall_score, _, usage = evaluate_entailment(api_client, gt_events, pred_description)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1

    # 计算Precision
    precision_score = 0
    if pred_events:
        precision_score, _, usage = evaluate_entailment(api_client, pred_events, gt_description)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1

    return {
        'idx': idx,
        'gt_description': gt_description,
        'gt_events': gt_events,
        'pred_description': pred_description,
        'pred_events': pred_events,
        'recall': recall_score,
        'precision': precision_score,
        'sample_stats': sample_stats,
    }


def process_mvbench_sample(item: Dict, api_client: BaseAPIClient, n_frames: int, stats: EvalStats) -> Dict:
    """处理单个MVBench样本 (多选题)"""
    video_name = item.get('video', '')
    question = item.get('question', '')
    candidates = item.get('candidates', [])
    answer = item.get('answer', '')

    video_path = PROJECT_DIR / "LMUData" / "datasets" / "MVBench" / "video" / video_name

    sample_stats = {
        'total_duration': 0.0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'api_calls': 0,
    }

    # 构建多选题prompt
    options_text = "\n".join([f"{chr(65+i)}. {opt}" for i, opt in enumerate(candidates)])
    prompt = f"""请根据视频内容回答以下多选题，只输出选项字母（A、B、C或D），不要输出其他内容。

视频问题: {question}

选项:
{options_text}

答案 (只输出字母):"""

    # 生成预测
    frames, temp_dir = extract_frames(str(video_path), n_frames=n_frames)

    content = []
    for frame_path in frames:
        b64_url = frame_to_base64(frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": b64_url}
        })
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    pred_answer, usage = api_client.chat(messages, max_tokens=10, temperature=0.0)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # 提取预测的选项字母
    pred_letter = pred_answer.strip()[0].upper() if pred_answer.strip() else ""
    correct_letter = answer.strip()[0].upper() if answer.strip() else ""

    # 计算是否正确
    is_correct = pred_letter == correct_letter

    return {
        'video': video_name,
        'question': question,
        'candidates': candidates,
        'gt_answer': answer,
        'pred_answer': pred_answer.strip(),
        'pred_letter': pred_letter,
        'correct_letter': correct_letter,
        'is_correct': is_correct,
        'sample_stats': sample_stats,
    }


def process_mmbench_video_sample(item: Dict, answer_map: Dict, api_client: BaseAPIClient, n_frames: int, stats: EvalStats) -> Dict:
    """处理单个MMBench-Video样本 (开放问答)"""
    video_name = item.get('video_name', '')
    question_id = item.get('question_id', '')
    question = item.get('question', '')

    # 从answer_map获取答案
    gt_answer = answer_map.get(question_id, {}).get('answer', '')

    video_path = PROJECT_DIR / "LMUData" / "datasets" / "MMBench-Video" / "video_pkl" / video_name

    sample_stats = {
        'total_duration': 0.0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'api_calls': 0,
    }

    # 构建prompt
    prompt = f"""请根据视频内容回答以下问题，用简短的句子回答。

问题: {question}

答案:"""

    # 生成预测
    frames, temp_dir = extract_frames(str(video_path), n_frames=n_frames)

    content = []
    for frame_path in frames:
        b64_url = frame_to_base64(frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": b64_url}
        })
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    pred_answer, usage = api_client.chat(messages, max_tokens=256, temperature=0.0)
    if usage:
        sample_stats['total_duration'] += usage.get('duration', 0)
        sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
        sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
        sample_stats['api_calls'] += 1

    # GPT评估答案相似度 (简化版：检查关键词重叠)
    similarity = calculate_answer_similarity(pred_answer.strip(), gt_answer)

    return {
        'video_name': video_name,
        'question_id': question_id,
        'question': question,
        'gt_answer': gt_answer,
        'pred_answer': pred_answer.strip(),
        'similarity': similarity,
        'sample_stats': sample_stats,
    }


def process_moviechat_test_sample(item: Dict, api_client: BaseAPIClient, n_frames: int, stats: EvalStats) -> Dict:
    """处理单个MovieChat-1K-test样本"""
    info = item.get('info', {})
    video_path_name = info.get('video_path', '')
    global_qas = item.get('global', [])
    breakpoint_qas = item.get('breakpoint', [])

    video_path = PROJECT_DIR / "LMUData" / "datasets" / "MovieChat-1K-test" / "videos" / video_path_name

    sample_stats = {
        'total_duration': 0.0,
        'total_input_tokens': 0,
        'total_output_tokens': 0,
        'api_calls': 0,
    }

    results = {
        'video_path': video_path_name,
        'global_results': [],
        'breakpoint_results': [],
        'sample_stats': sample_stats,
    }

    # 处理全局问题
    for qa in global_qas:
        question = qa.get('question', '')
        prompt = f"请根据视频内容回答以下问题，用简短的句子回答。\n\n问题: {question}\n\n答案:"
        pred_answer, usage = call_video_qa(api_client, str(video_path), prompt, n_frames)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1
        results['global_results'].append({
            'question': question,
            'pred_answer': pred_answer.strip() if pred_answer else ''
        })

    # 处理断点问题
    for qa in breakpoint_qas:
        time_point = qa.get('time', 0)
        question = qa.get('question', '')
        prompt = f"请根据视频内容回答以下问题，用简短的句子回答。\n\n问题: {question}\n\n答案:"
        pred_answer, usage = call_video_qa(api_client, str(video_path), prompt, n_frames)
        if usage:
            sample_stats['total_duration'] += usage.get('duration', 0)
            sample_stats['total_input_tokens'] += usage.get('prompt_tokens', 0)
            sample_stats['total_output_tokens'] += usage.get('completion_tokens', 0)
            sample_stats['api_calls'] += 1
        results['breakpoint_results'].append({
            'time': time_point,
            'question': question,
            'pred_answer': pred_answer.strip() if pred_answer else ''
        })

    return results


def call_video_qa(api_client: BaseAPIClient, video_path: str, prompt: str, n_frames: int) -> Tuple[str, Optional[Dict]]:
    """调用视频问答API"""
    frames, temp_dir = extract_frames(video_path, n_frames=n_frames)

    content = []
    for frame_path in frames:
        b64_url = frame_to_base64(frame_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": b64_url}
        })
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

    for retry in range(3):
        result, usage = api_client.chat(messages, max_tokens=256, temperature=0.0)
        if result and not result.startswith("ERROR"):
            return result, usage
        time.sleep(2)

    return "ERROR: Failed", None


def calculate_answer_similarity(pred: str, gt: str) -> float:
    """计算预测答案与标准答案的相似度 (简化版)"""
    pred_words = set(pred.lower().split())
    gt_words = set(gt.lower().split())

    if not pred_words or not gt_words:
        return 0.0

    intersection = pred_words & gt_words
    union = pred_words | gt_words

    return len(intersection) / len(union) if union else 0.0


def get_dataset_metadata(dataset_name: str) -> Tuple[Path, Path, str]:
    """获取数据集元数据路径"""
    if dataset_name == "dream1k":
        dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "dream1k"
        metadata_path = dataset_dir / "json" / "metadata.json"
        video_dir = dataset_dir / "video"
        idx_field = "idx"
    elif dataset_name == "mmbench_video":
        dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MMBench-Video"
        metadata_path = dataset_dir / "MMBench-Video_q.json"
        answer_path = dataset_dir / "MMBench-Video_a.json"
        video_dir = dataset_dir / "video_pkl"
        idx_field = "question_id"
        return metadata_path, video_dir, idx_field, answer_path
    elif dataset_name == "mvbench":
        dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MVBench"
        # MVBench has multiple JSON files for different tasks
        metadata_path = dataset_dir / "json"
        video_dir = dataset_dir / "video"
        idx_field = "video"
        return metadata_path, video_dir, idx_field, None
    elif dataset_name == "moviechat1k":
        dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MovieChat-1K-test"
        metadata_path = dataset_dir / "annotations"
        video_dir = dataset_dir / "videos"
        idx_field = "video_path"
        return metadata_path, video_dir, idx_field, None
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    return metadata_path, video_dir, idx_field, None


def run_evaluation(args):
    """运行评测"""
    print("=" * 80)
    print(f"视频理解评测 - {args.dataset.upper()} 数据集")
    print("=" * 80)
    print(f"\n模型配置:")
    print(f"  类型: {args.model}")
    if args.model == "agent":
        print(f"  URL: {args.base_url}/chat/completions")
        print(f"  Auth Token: {args.auth_token[:10]}...")
    elif args.model == "doubao":
        print(f"  Base URL: {args.base_url}")
        print(f"  Model: {args.model_name}")
    else:
        print(f"  Base URL: {args.base_url}")
        print(f"  Model: {args.model_name}")

    # 创建模型配置
    config = ModelConfig(
        model_type=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
        model_name=args.model_name,
        auth_token=args.auth_token
    )

    # 创建API客户端
    stats = EvalStats()
    api_client = create_api_client(config, stats)

    # 获取数据集
    print(f"\n[1/5] 加载数据集元数据...")

    if args.dataset == "dream1k":
        annotations = load_dream1k_dataset(args)
    elif args.dataset == "mmbench_video":
        annotations = load_mmbench_video_dataset(args)
    elif args.dataset == "mvbench":
        annotations = load_mvbench_dataset(args)
    elif args.dataset == "moviechat1k":
        annotations = load_moviechat1k_dataset(args)
    else:
        print(f"  错误: 未知数据集 {args.dataset}")
        return 1

    print(f"  加载了 {len(annotations)} 个样本")

    test_samples = annotations[args.start:args.start + args.max_samples]
    print(f"  将测试样本 {args.start} ~ {args.start + len(test_samples) - 1}")

    # 输出目录
    output_dir = PROJECT_DIR / "outputs" / f"{args.dataset}_evaluation" / args.model
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n  输出目录: {output_dir}")

    # 处理样本
    overall_start_time = time.time()
    results = []

    print(f"\n[2/5] 处理样本 (并发数: {args.workers})...")

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        if args.dataset == "dream1k":
            futures = {executor.submit(process_dream1k_sample, item, api_client, args.n_frames, stats): i
                       for i, item in enumerate(test_samples)}
        elif args.dataset == "mmbench_video":
            # 加载答案映射
            answer_map = load_mmbench_answers()
            futures = {executor.submit(process_mmbench_video_sample, item, answer_map, api_client, args.n_frames, stats): i
                       for i, item in enumerate(test_samples)}
        elif args.dataset == "mvbench":
            futures = {executor.submit(process_mvbench_sample, item, api_client, args.n_frames, stats): i
                       for i, item in enumerate(test_samples)}
        elif args.dataset == "moviechat1k":
            futures = {executor.submit(process_moviechat_test_sample, item, api_client, args.n_frames, stats): i
                       for i, item in enumerate(test_samples)}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing"):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                idx = futures[future]
                results.append({
                    'idx': test_samples[idx].get('idx', idx),
                    'error': str(e),
                    'recall': 0,
                    'precision': 0,
                    'sample_stats': {'total_duration': 0, 'total_input_tokens': 0,
                                   'total_output_tokens': 0, 'api_calls': 0}
                })

            if len(results) % 10 == 0:
                with open(output_dir / "partial_results.json", 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)

    # 按idx排序
    results.sort(key=lambda x: x.get('idx', x.get('question_id', x.get('video', 0))))

    overall_duration = time.time() - overall_start_time

    print(f"\n[3/5] 计算总体指标...")

    # 根据数据集计算不同指标
    if args.dataset == "dream1k":
        metrics = calculate_dream1k_metrics(results, stats, overall_duration)
    elif args.dataset == "mmbench_video":
        metrics = calculate_mmbench_metrics(results, stats, overall_duration)
    elif args.dataset == "mvbench":
        metrics = calculate_mvbench_metrics(results, stats, overall_duration)
    elif args.dataset == "moviechat1k":
        metrics = calculate_moviechat_metrics(results, stats, overall_duration)

    print(f"\n[4/5] 汇总统计...")

    print(f"\n{'='*80}")
    print(f"{args.dataset.upper()} 评测结果")
    print(f"{'='*80}")
    print(f"\n【评测指标】")
    for key, value in metrics['metrics'].items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2%}" if 'rate' in key or 'score' in key or 'accuracy' in key else f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    print(f"\n【时间统计】")
    print(f"  总耗时: {metrics['time_stats']['total_duration_seconds']:.1f}秒 ({metrics['time_stats']['total_duration_minutes']:.1f}分钟)")
    print(f"  API调用总耗时: {metrics['time_stats']['api_total_duration_seconds']:.1f}秒")
    print(f"  平均每样本耗时: {metrics['time_stats']['avg_per_sample_seconds']:.1f}秒")
    print(f"  平均每次API耗时: {metrics['time_stats']['avg_per_api_call_seconds']:.2f}秒")

    print(f"\n【Token统计】")
    print(f"  API总请求次数: {metrics['token_stats']['total_api_calls']}")
    print(f"  总Input Tokens: {metrics['token_stats']['total_input_tokens']:,}")
    print(f"  总Output Tokens: {metrics['token_stats']['total_output_tokens']:,}")
    print(f"  总Tokens: {metrics['token_stats']['total_tokens']:,}")
    print(f"{'='*80}")

    print(f"\n[5/5] 保存结果...")
    result_file = output_dir / "results.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'model_type': args.model,
            'model_name': args.model_name or args.model,
            'dataset': args.dataset,
            'test_date': time.strftime('%Y-%m-%d'),
            'start_idx': args.start,
            'num_samples': len(results),
            'n_frames': args.n_frames,
            'workers': args.workers,
            **metrics
        }, f, ensure_ascii=False, indent=2)

    report_file = output_dir / "evaluation_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write(f"{args.dataset.upper()} 评测结果\n")
        f.write("="*80 + "\n\n")
        f.write(f"模型类型: {args.model}\n")
        f.write(f"模型名称: {args.model_name or args.model}\n")
        f.write(f"评测日期: {time.strftime('%Y-%m-%d')}\n")
        f.write(f"样本范围: {args.start} ~ {args.start + len(results) - 1}\n")
        f.write(f"帧数: {args.n_frames}\n")
        f.write(f"并发线程数: {args.workers}\n\n")

        f.write("-"*80 + "\n")
        f.write("评测指标\n")
        f.write("-"*80 + "\n")
        for key, value in metrics['metrics'].items():
            if isinstance(value, float):
                f.write(f"  {key}: {value:.2%}\n" if 'rate' in key or 'score' in key or 'accuracy' in key else f"  {key}: {value:.2f}\n")
            else:
                f.write(f"  {key}: {value}\n")

        f.write("-"*80 + "\n")
        f.write("时间统计\n")
        f.write("-"*80 + "\n")
        f.write(f"  总耗时: {metrics['time_stats']['total_duration_seconds']:.1f}秒 ({metrics['time_stats']['total_duration_minutes']:.1f}分钟)\n")
        f.write(f"  API调用总耗时: {metrics['time_stats']['api_total_duration_seconds']:.1f}秒\n")
        f.write(f"  平均每样本耗时: {metrics['time_stats']['avg_per_sample_seconds']:.1f}秒\n")
        f.write(f"  平均每样本API耗时: {metrics['time_stats']['avg_per_sample_seconds']:.1f}秒\n")
        f.write(f"  平均每次API耗时: {metrics['time_stats']['avg_per_api_call_seconds']:.2f}秒\n\n")

        f.write("-"*80 + "\n")
        f.write("Token统计\n")
        f.write("-"*80 + "\n")
        f.write(f"  API总请求次数: {metrics['token_stats']['total_api_calls']}\n")
        f.write(f"  总Input Tokens: {metrics['token_stats']['total_input_tokens']:,}\n")
        f.write(f"  总Output Tokens: {metrics['token_stats']['total_output_tokens']:,}\n")
        f.write(f"  总Tokens: {metrics['token_stats']['total_tokens']:,}\n")
        f.write(f"  平均每样本Input Tokens: {metrics['token_stats']['avg_input_tokens_per_sample']:,.0f}\n")
        f.write(f"  平均每样本Output Tokens: {metrics['token_stats']['avg_output_tokens_per_sample']:,.0f}\n")
        f.write(f"  平均每次API Input Tokens: {metrics['token_stats']['avg_input_tokens_per_api_call']:,.0f}\n")
        f.write(f"  平均每次API Output Tokens: {metrics['token_stats']['avg_output_tokens_per_api_call']:,.0f}\n\n")

        if 'metric_description' in metrics:
            f.write("-"*80 + "\n")
            f.write("指标说明\n")
            f.write("-"*80 + "\n")
            for desc in metrics['metric_description']:
                f.write(f"  {desc}\n")
        f.write("="*80 + "\n")

    print(f"  结果已保存: {result_file}")
    print(f"  报告已保存: {report_file}")
    print(f"\n评测完成！")

    return 0


def load_dream1k_dataset(args):
    """加载DREAM-1K数据集"""
    dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "dream1k"
    metadata_path = dataset_dir / "json" / "metadata.json"

    if not metadata_path.exists():
        raise FileNotFoundError(f"元数据文件不存在: {metadata_path}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_mmbench_video_dataset(args):
    """加载MMBench-Video数据集"""
    dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MMBench-Video"
    questions_path = dataset_dir / "MMBench-Video_q.json"

    if not questions_path.exists():
        raise FileNotFoundError(f"元数据文件不存在: {questions_path}")

    with open(questions_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_mmbench_answers() -> Dict:
    """加载MMBench-Video答案映射"""
    dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MMBench-Video"
    answers_path = dataset_dir / "MMBench-Video_a.json"

    with open(answers_path, 'r', encoding='utf-8') as f:
        answers = json.load(f)

    # 构建question_id -> answer映射
    return {a['question_id']: a for a in answers}


def load_mvbench_dataset(args) -> List[Dict]:
    """加载MVBench数据集 (所有任务类别合并)"""
    import glob
    dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MVBench"
    json_dir = dataset_dir / "json"

    all_samples = []
    json_files = list(json_dir.glob("*.json"))

    for json_file in json_files:
        with open(json_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)
            if isinstance(samples, list):
                # 添加任务类别信息
                task_name = json_file.stem
                for sample in samples:
                    sample['_task_category'] = task_name
                all_samples.extend(samples)

    return all_samples


def load_moviechat1k_dataset(args) -> List[Dict]:
    """加载MovieChat-1K-test数据集"""
    dataset_dir = PROJECT_DIR / "LMUData" / "datasets" / "MovieChat-1K-test"
    annotations_dir = dataset_dir / "annotations"

    all_samples = []
    for annot_file in annotations_dir.glob("*.json"):
        with open(annot_file, 'r', encoding='utf-8') as f:
            all_samples.append(json.load(f))

    return all_samples


def calculate_dream1k_metrics(results, stats, overall_duration):
    """计算DREAM-1K数据集的指标"""
    recalls = [r['recall'] for r in results if 'recall' in r]
    precisions = [r['precision'] for r in results if 'precision' in r]

    avg_recall = sum(recalls) / len(recalls) if recalls else 0
    avg_precision = sum(precisions) / len(precisions) if precisions else 0
    f1 = 2 * avg_recall * avg_precision / (avg_recall + avg_precision) if (avg_recall + avg_precision) > 0 else 0

    total_input = stats.total_input_tokens
    total_output = stats.total_output_tokens
    total_tokens = total_input + total_output
    total_api_time = stats.total_duration
    n_requests = stats.total_requests

    return {
        'metrics': {
            'action_recall': float(avg_recall),
            'action_precision': float(avg_precision),
            'f1_score': float(f1),
        },
        'time_stats': {
            'total_duration_seconds': overall_duration,
            'total_duration_minutes': overall_duration / 60,
            'api_total_duration_seconds': total_api_time,
            'avg_per_sample_seconds': overall_duration / len(results),
            'avg_per_api_call_seconds': total_api_time / n_requests if n_requests > 0 else 0,
        },
        'token_stats': {
            'total_api_calls': n_requests,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'avg_input_tokens_per_sample': total_input / len(results),
            'avg_output_tokens_per_sample': total_output / len(results),
            'avg_total_tokens_per_sample': total_tokens / len(results),
            'avg_input_tokens_per_api_call': total_input / n_requests if n_requests > 0 else 0,
            'avg_output_tokens_per_api_call': total_output / n_requests if n_requests > 0 else 0,
            'avg_total_tokens_per_api_call': total_tokens / n_requests if n_requests > 0 else 0,
        },
        'metric_description': [
            'Action Recall: GT事件被预测描述蕴涵的比例',
            'Action Precision: 预测事件被GT描述蕴涵的比例',
            'F1 Score: 2 * R * P / (R + P)',
        ]
    }


def calculate_mmbench_metrics(results, stats, overall_duration):
    """计算MMBench-Video数据集的指标"""
    similarities = [r['similarity'] for r in results if 'similarity' in r]
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0

    total_input = stats.total_input_tokens
    total_output = stats.total_output_tokens
    total_tokens = total_input + total_output
    total_api_time = stats.total_duration
    n_requests = stats.total_requests

    return {
        'metrics': {
            'avg_answer_similarity': float(avg_similarity),
        },
        'time_stats': {
            'total_duration_seconds': overall_duration,
            'total_duration_minutes': overall_duration / 60,
            'api_total_duration_seconds': total_api_time,
            'avg_per_sample_seconds': overall_duration / len(results),
            'avg_per_api_call_seconds': total_api_time / n_requests if n_requests > 0 else 0,
        },
        'token_stats': {
            'total_api_calls': n_requests,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'avg_input_tokens_per_sample': total_input / len(results),
            'avg_output_tokens_per_sample': total_output / len(results),
            'avg_total_tokens_per_sample': total_tokens / len(results),
            'avg_input_tokens_per_api_call': total_input / n_requests if n_requests > 0 else 0,
            'avg_output_tokens_per_api_call': total_output / n_requests if n_requests > 0 else 0,
            'avg_total_tokens_per_api_call': total_tokens / n_requests if n_requests > 0 else 0,
        },
        'metric_description': [
            'Avg Answer Similarity: 预测答案与标准答案的词汇相似度 (Jaccard)',
        ]
    }


def calculate_mvbench_metrics(results, stats, overall_duration):
    """计算MVBench数据集的指标"""
    correct_count = sum(1 for r in results if r.get('is_correct', False))
    accuracy = correct_count / len(results) if results else 0

    # 按任务类别统计
    task_stats = {}
    for r in results:
        task = r.get('_task_category', 'unknown')
        if task not in task_stats:
            task_stats[task] = {'correct': 0, 'total': 0}
        task_stats[task]['total'] += 1
        if r.get('is_correct', False):
            task_stats[task]['correct'] += 1

    total_input = stats.total_input_tokens
    total_output = stats.total_output_tokens
    total_tokens = total_input + total_output
    total_api_time = stats.total_duration
    n_requests = stats.total_requests

    return {
        'metrics': {
            'overall_accuracy': float(accuracy),
            'correct_count': correct_count,
            'total_samples': len(results),
            'task_category_accuracy': {
                task: stats['correct'] / stats['total']
                for task, stats in task_stats.items()
            },
        },
        'time_stats': {
            'total_duration_seconds': overall_duration,
            'total_duration_minutes': overall_duration / 60,
            'api_total_duration_seconds': total_api_time,
            'avg_per_sample_seconds': overall_duration / len(results),
            'avg_per_api_call_seconds': total_api_time / n_requests if n_requests > 0 else 0,
        },
        'token_stats': {
            'total_api_calls': n_requests,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'avg_input_tokens_per_sample': total_input / len(results),
            'avg_output_tokens_per_sample': total_output / len(results),
            'avg_total_tokens_per_sample': total_tokens / len(results),
            'avg_input_tokens_per_api_call': total_input / n_requests if n_requests > 0 else 0,
            'avg_output_tokens_per_api_call': total_output / n_requests if n_requests > 0 else 0,
            'avg_total_tokens_per_api_call': total_tokens / n_requests if n_requests > 0 else 0,
        },
        'metric_description': [
            'Overall Accuracy: 多选题正确率',
        ]
    }


def calculate_moviechat_metrics(results, stats, overall_duration):
    """计算MovieChat-1K-test数据集的指标"""
    total_questions = 0
    total_input = stats.total_input_tokens
    total_output = stats.total_output_tokens
    total_tokens = total_input + total_output
    total_api_time = stats.total_duration
    n_requests = stats.total_requests

    return {
        'metrics': {
            'total_videos': len(results),
            'total_questions': total_questions,
        },
        'time_stats': {
            'total_duration_seconds': overall_duration,
            'total_duration_minutes': overall_duration / 60,
            'api_total_duration_seconds': total_api_time,
            'avg_per_sample_seconds': overall_duration / len(results),
            'avg_per_api_call_seconds': total_api_time / n_requests if n_requests > 0 else 0,
        },
        'token_stats': {
            'total_api_calls': n_requests,
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'avg_input_tokens_per_sample': total_input / len(results),
            'avg_output_tokens_per_sample': total_output / len(results),
            'avg_total_tokens_per_sample': total_tokens / len(results),
            'avg_input_tokens_per_api_call': total_input / n_requests if n_requests > 0 else 0,
            'avg_output_tokens_per_api_call': total_output / n_requests if n_requests > 0 else 0,
            'avg_total_tokens_per_api_call': total_tokens / n_requests if n_requests > 0 else 0,
        },
        'metric_description': [
            'MovieChat-1K: 全局问答+断点问答数据集',
        ]
    }


def main():
    parser = argparse.ArgumentParser(
        description="统一评测框架 - 支持多模型多数据集评测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 测试本地agent - DREAM-1K
  python bench/evaluate.py --model agent --dataset dream1k --max-samples 10

  # 测试本地agent - MMBench-Video
  python bench/evaluate.py --model agent --dataset mmbench_video --max-samples 10

  # 测试本地agent - MVBench
  python bench/evaluate.py --model agent --dataset mvbench --max-samples 10

  # 测试本地agent - MovieChat-1K
  python bench/evaluate.py --model agent --dataset moviechat1k --max-samples 10

  # 测试豆包直接API
  python bench/evaluate.py --model doubao --dataset dream1k --max-samples 10

  # 测试其他OpenAI兼容API
  python bench/evaluate.py --model openai --base-url http://host:port/v1 \\
       --api-key xxx --model-name gpt-4v --dataset dream1k --max-samples 10
        """
    )

    # 模型配置
    parser.add_argument('--model', type=str, default='agent',
                       choices=['agent', 'doubao', 'openai'],
                       help='模型类型: agent(本地智能体), doubao(豆包API), openai(通用OpenAI兼容API)')
    parser.add_argument('--base-url', type=str, default='',
                       help='API base URL')
    parser.add_argument('--api-key', type=str, default='',
                       help='API密钥')
    parser.add_argument('--model-name', type=str, default='',
                       help='模型名称')
    parser.add_argument('--auth-token', type=str, default='sk-admin',
                       help='智能体API认证Token')

    # 数据集配置
    parser.add_argument('--dataset', type=str, default='dream1k',
                       choices=['dream1k', 'mmbench_video', 'mvbench', 'moviechat1k'],
                       help='评测数据集: dream1k(DREAM-1K事件理解), mmbench_video(MMBench-Video开放问答), '
                            'mvbench(MVBench多选题), moviechat1k(MovieChat-1K全局+断点问答)')
    parser.add_argument('--start', type=int, default=0,
                       help='起始样本索引')
    parser.add_argument('--max-samples', type=int, default=100,
                       help='最大测试样本数')
    parser.add_argument('--n-frames', type=int, default=16,
                       help='每视频抽帧数量')

    # 并发配置
    parser.add_argument('--workers', type=int, default=8,
                       help='并发线程数')

    args = parser.parse_args()

    # 设置默认URL
    if args.model == 'agent' and not args.base_url:
        args.base_url = 'http://localhost:18080/v1'
    elif args.model == 'doubao' and not args.base_url:
        # 从配置文件加载豆包配置
        load_config()
        args.base_url = os.environ.get('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
        args.api_key = os.environ.get('DOUBAO_API_KEY', '')
        args.model_name = os.environ.get('DOUBAO_MODEL', 'doubao-seed-1-8-251228')
    elif args.model == 'openai' and not args.base_url:
        print("错误: --openai 模型需要指定 --base-url")
        return 1

    return run_evaluation(args)


if __name__ == "__main__":
    sys.exit(main())
