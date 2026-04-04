"""
视频处理工具 - 包含智能动态抽帧算法

支持：
1. 均匀抽帧 (extract_uniform) - 固定间隔抽帧
2. 自适应抽帧 (extract_adaptive) - 基于内容变化的智能抽帧
3. 关键帧抽帧 (extract_keyframes) - 使用VLM识别关键帧
"""

import os
import json
import subprocess
import tempfile
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path

from ..cache import DiskCache


@dataclass
class FrameInfo:
    """帧信息"""
    frame_idx: int
    timestamp: float
    path: str
    quality: float = 0.0  # 质量分数（用于关键帧选择）


class VideoFrameExtractor:
    """视频帧提取器"""

    def __init__(self, cache: DiskCache):
        self.cache = cache

    def _probe_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path,
        ]
        try:
            p = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            data = json.loads(p.stdout.decode("utf-8"))
            dur = float(data["format"]["duration"])
            return dur if dur > 0 else 0.0
        except:
            return 0.0

    def extract_uniform(
        self,
        video_path: str,
        *,
        n_frames: int = 16
    ) -> List[str]:
        """
        均匀抽帧 - 固定间隔抽帧

        Args:
            video_path: 视频路径
            n_frames: 抽帧数量

        Returns:
            帧图片路径列表
        """
        key = self.cache.key_for_file(video_path, {"tool": "extract_uniform", "n_frames": n_frames})
        cached = self.cache.get_json(key)
        if isinstance(cached, list) and all(isinstance(x, str) for x in cached) and all(Path(x).exists() for x in cached):
            return cached

        duration = self._probe_duration(video_path)
        if duration <= 0:
            duration = 60.0

        fps = max(0.1, n_frames / duration)

        temp_dir = Path(tempfile.mkdtemp(prefix="frames_uniform_"))
        out_pattern = str(temp_dir / "%05d.jpg")

        cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}", "-q:v", "2", out_pattern]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

        frames = sorted(str(p) for p in temp_dir.glob("*.jpg"))
        if len(frames) > n_frames:
            step = max(1, len(frames) // n_frames)
            frames = frames[::step][:n_frames]

        self.cache.set_json(key, frames)
        return frames

    def extract_adaptive(
        self,
        video_path: str,
        *,
        min_frames: int = 8,
        max_frames: int = 32,
        threshold: float = 0.3,
        use_vlm: bool = False
    ) -> List[Tuple[str, float]]:
        """
        自适应抽帧 - 基于内容变化的智能抽帧算法

        算法原理：
        1. 均匀抽取候选帧
        2. 计算相邻帧的特征差异（颜色直方图/边缘/光流）
        3. 变化超过阈值时保留该帧
        4. 保证最少min_frames，最多max_frames

        Args:
            video_path: 视频路径
            min_frames: 最少帧数
            max_frames: 最多帧数
            threshold: 变化阈值 (0-1)
            use_vlm: 是否使用VLM辅助关键帧识别

        Returns:
            [(帧路径, 时间戳), ...]
        """
        key = self.cache.key_for_file(
            video_path,
            {"tool": "extract_adaptive", "min": min_frames, "max": max_frames, "threshold": threshold}
        )
        cached = self.cache.get_json(key)
        if cached:
            return [(c["path"], c["timestamp"]) for c in cached]

        duration = self._probe_duration(video_path)
        if duration <= 0:
            duration = 60.0

        # Step 1: 均匀抽取候选帧（比目标数量多）
        candidate_count = max_frames * 3
        fps = candidate_count / duration

        temp_dir = Path(tempfile.mkdtemp(prefix="frames_candidate_"))
        out_pattern = str(temp_dir / "%05d.jpg")

        cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}", "-q:v", "2", out_pattern]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

        candidate_frames = sorted(temp_dir.glob("*.jpg"))
        if not candidate_frames:
            # 回退到均匀抽帧
            frames = self.extract_uniform(video_path, n_frames=min_frames)
            return [(f, i * duration / len(frames)) for i, f in enumerate(frames)]

        # Step 2: 计算帧差异
        frame_diffs = self._compute_frame_differences(list(candidate_frames))

        # Step 3: 基于变化选择关键帧
        selected_indices = self._select_key_frames(
            frame_diffs,
            min_frames=min_frames,
            max_frames=max_frames,
            threshold=threshold
        )

        # Step 4: 如果选择太少，回退到均匀选择
        if len(selected_indices) < min_frames:
            indices = np.linspace(0, len(candidate_frames) - 1, min_frames, dtype=int)
            selected_indices = sorted(set(indices.tolist()))

        # Step 5: 如果选择太多，均匀稀疏化
        if len(selected_indices) > max_frames:
            step = len(selected_indices) // max_frames
            selected_indices = selected_indices[::step][:max_frames]

        # 构建结果
        results = []
        for idx in sorted(selected_indices):
            frame_path = str(candidate_frames[idx])
            timestamp = idx * (duration / len(candidate_frames))
            results.append((frame_path, timestamp))

        # 清理未选中的候选帧
        for i, frame_path in enumerate(candidate_frames):
            if i not in selected_indices:
                try:
                    frame_path.unlink()
                except:
                    pass
        try:
            temp_dir.rmdir()
        except:
            pass

        # 缓存结果
        self.cache.set_json(key, [{"path": r[0], "timestamp": r[1]} for r in results])
        return results

    def _compute_frame_differences(self, frame_paths: List[Path]) -> List[float]:
        """
        计算相邻帧的差异分数

        使用颜色直方图方法：
        - 计算每帧的RGB直方图
        - 计算相邻帧直方图的卡方距离
        """
        if len(frame_paths) < 2:
            return [0.0]

        diffs = [0.0]  # 第一帧差异为0

        prev_hist = self._compute_color_histogram(frame_paths[0])

        for frame_path in frame_paths[1:]:
            curr_hist = self._compute_color_histogram(frame_path)

            # 计算卡方距离
            diff = self._chi_square_distance(prev_hist, curr_hist)
            diffs.append(diff)
            prev_hist = curr_hist

        # 归一化
        max_diff = max(diffs) if max(diffs) > 0 else 1.0
        normalized_diffs = [d / max_diff for d in diffs]

        return normalized_diffs

    def _compute_color_histogram(self, image_path: Path) -> np.ndarray:
        """计算RGB颜色直方图"""
        try:
            from PIL import Image
            img = Image.open(image_path).convert("RGB")
            img = img.resize((64, 64))  # 缩小加速

            # 计算直方图
            r_hist = np.array(img.getchannel(0).histogram())
            g_hist = np.array(img.getchannel(1).histogram())
            b_hist = np.array(img.getchannel(2).histogram())

            # 归一化
            r_hist = r_hist / (r_hist.sum() + 1e-10)
            g_hist = g_hist / (g_hist.sum() + 1e-10)
            b_hist = b_hist / (b_hist.sum() + 1e-10)

            return np.concatenate([r_hist, g_hist, b_hist])
        except:
            return np.zeros(768)  # 64*3*4 bins

    def _chi_square_distance(self, hist1: np.ndarray, hist2: np.ndarray) -> float:
        """计算卡方距离"""
        diff = hist1 - hist2
        denom = hist1 + hist2 + 1e-10
        chi_sq = np.sum(diff * diff / denom)
        return chi_sq

    def _select_key_frames(
        self,
        diffs: List[float],
        min_frames: int,
        max_frames: int,
        threshold: float
    ) -> List[int]:
        """
        基于差异选择关键帧

        策略：
        1. 差异超过阈值时选择该帧
        2. 确保最小间隔（避免选择太近的帧）
        3. 始终选择首尾帧
        """
        selected = [0]  # 首帧
        min_interval = max(1, len(diffs) // max_frames)

        for i in range(1, len(diffs) - 1):
            if diffs[i] >= threshold:
                # 检查与上一个选中帧的间隔
                if not selected or i - selected[-1] >= min_interval:
                    selected.append(i)

        # 如果选太少，强制均匀选择
        if len(selected) < min_frames:
            indices = np.linspace(0, len(diffs) - 1, min_frames, dtype=int)
            selected = sorted(set(indices.tolist()))

        # 确保末帧被选中
        if selected[-1] != len(diffs) - 1:
            selected.append(len(diffs) - 1)

        return sorted(set(selected))

    def extract_keyframes_vlm(
        self,
        video_path: str,
        vllm_client,
        *,
        max_frames: int = 8,
        prompt: str = "这个画面是否包含重要的视觉变化，如物体出现/消失、动作变化、场景切换？请回答是或否。"
    ) -> List[Tuple[str, float]]:
        """
        使用VLM辅助识别关键帧

        Args:
            video_path: 视频路径
            vllm_client: vLLM客户端
            max_frames: 最大关键帧数
            prompt: 关键帧判断提示

        Returns:
            [(帧路径, 时间戳), ...]
        """
        duration = self._probe_duration(video_path)
        if duration <= 0:
            duration = 60.0

        # 先均匀抽取候选帧
        candidates = self.extract_adaptive(
            video_path,
            min_frames=max_frames * 2,
            max_frames=max_frames * 3
        )

        if not candidates:
            return []

        # 使用VLM判断每帧是否重要
        key_frames = []
        for frame_path, timestamp in candidates:
            try:
                with open(frame_path, 'rb') as f:
                    img_bytes = f.read()

                response = vllm_client.caption_image(
                    img_bytes,
                    prompt=prompt
                )

                # 简单判断是否重要
                is_key = any(kw in response.lower() for kw in ['是', 'yes', '变化', '重要', '关键'])
                if is_key:
                    key_frames.append((frame_path, timestamp))

            except Exception:
                continue

        # 如果VLM选择太少，回退到自适应选择
        if len(key_frames) < max_frames // 2:
            return candidates[:max_frames]

        # 如果选择太多，均匀稀疏化
        if len(key_frames) > max_frames:
            step = len(key_frames) // max_frames
            key_frames = key_frames[::step][:max_frames]

        return key_frames
