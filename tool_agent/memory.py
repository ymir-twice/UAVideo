"""
长短期记忆管理系统

基于开题报告设计的分层记忆结构：
- 短期记忆：滑动时间窗口内的帧级描述
- 长期记忆：语义片段的分层组织
"""

import uuid
import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path


@dataclass
class Frame记忆:
    """单帧的记忆单元"""
    frame_idx: int
    timestamp: float  # 秒
    caption: str = ""  # 画面描述
    audio_text: str = ""  # 该时间点的音频
    frame_path: str = ""  # 帧图片路径
    importance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Frame记忆":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class 语义片段:
    """语义片段 - 长期记忆单元"""
    segment_id: str
    start_time: float
    end_time: float
    summary: str = ""  # 片段摘要
    key_frames: List[str] = field(default_factory=list)  # 关键帧描述
    entities: List[str] = field(default_factory=list)  # 关键实体
    events: List[str] = field(default_factory=list)  # 关键事件
    importance_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "语义片段":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class 短期记忆:
    """短期记忆 - 滑动时间窗口内的帧级描述"""
    frames: List[Frame记忆] = field(default_factory=list)
    window_size: int = 50  # 最多保留50帧
    max_age_seconds: int = 300  # 5分钟内

    def add(self, frame: Frame记忆) -> None:
        """添加新帧记忆"""
        self.frames.append(frame)
        # 保持窗口大小
        if len(self.frames) > self.window_size:
            self.frames.pop(0)

    def get_recent(self, n: int = 10) -> List[Frame记忆]:
        """获取最近n帧记忆"""
        return self.frames[-n:] if self.frames else []

    def get_by_time_range(self, start: float, end: float) -> List[Frame记忆]:
        """获取指定时间范围内的记忆"""
        return [f for f in self.frames if start <= f.timestamp <= end]

    def prune_old(self, current_time: float) -> List[Frame记忆]:
        """清理过期记忆，返回被移除的记忆"""
        cutoff = current_time - self.max_age_seconds
        old_frames = [f for f in self.frames if f.timestamp < cutoff]
        self.frames = [f for f in self.frames if f.timestamp >= cutoff]
        return old_frames

    def to_context_text(self, max_chars: int = 4000) -> str:
        """转换为上下文文本"""
        if not self.frames:
            return ""

        lines = ["【短期记忆 - 最近帧描述】"]
        for f in self.frames[-20:]:  # 只取最近20帧
            parts = []
            if f.caption:
                parts.append(f"画面: {f.caption}")
            if f.audio_text:
                parts.append(f"音频: {f.audio_text}")
            if parts:
                lines.append(f"[{f.timestamp:.1f}s] {' | '.join(parts)}")

        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars - 20] + "\n[TRUNCATED]"
        return text

    def get_frames_summary(self) -> str:
        """获取帧列表摘要"""
        if not self.frames:
            return "暂无记忆"
        return f"{len(self.frames)}帧记忆，最近: {self.frames[-1].timestamp:.1f}s，最早: {self.frames[0].timestamp:.1f}s"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frames": [f.to_dict() for f in self.frames],
            "window_size": self.window_size,
            "max_age_seconds": self.max_age_seconds,
            "count": len(self.frames)
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "短期记忆":
        frames = [Frame记忆.from_dict(f) for f in d.get("frames", [])]
        return cls(
            frames=frames,
            window_size=d.get("window_size", 50),
            max_age_seconds=d.get("max_age_seconds", 300)
        )


@dataclass
class 长期记忆:
    """长期记忆 - 语义片段的分层组织"""
    segments: List[语义片段] = field(default_factory=list)
    max_segments: int = 20  # 最多保留20个片段

    def add_segment(self, segment: 语义片段) -> None:
        """添加语义片段"""
        self.segments.append(segment)
        # 按时间排序
        self.segments.sort(key=lambda s: s.start_time)
        # 保持最大数量
        if len(self.segments) > self.max_segments:
            # 移除最不重要的片段
            self.segments.sort(key=lambda s: s.importance_score, reverse=True)
            self.segments = self.segments[:self.max_segments]

    def get_relevant(self, query: str, top_k: int = 5) -> List[语义片段]:
        """根据查询检索相关片段（简单关键词匹配）"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for seg in self.segments:
            score = 0
            # 摘要匹配
            if query_lower in seg.summary.lower():
                score += 3
            # 实体匹配
            for entity in seg.entities:
                if entity.lower() in query_lower:
                    score += 2
            # 事件匹配
            for event in seg.events:
                if event.lower() in query_lower:
                    score += 2
            # 关键帧匹配
            for frame in seg.key_frames:
                if query_lower in frame.lower():
                    score += 1
            if score > 0:
                scored.append((score, seg))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:top_k]]

    def get_segment_at_time(self, timestamp: float) -> Optional[语义片段]:
        """获取包含指定时间的片段"""
        for seg in self.segments:
            if seg.start_time <= timestamp <= seg.end_time:
                return seg
        return None

    def to_context_text(self, query: str = "", max_chars: int = 6000) -> str:
        """转换为上下文文本"""
        if not self.segments:
            return ""

        relevant = self.get_relevant(query, top_k=10) if query else self.segments[-5:]

        lines = ["【长期记忆 - 语义片段】"]
        for i, seg in enumerate(relevant, 1):
            lines.append(f"\n## 片段{i} [{seg.start_time:.1f}s - {seg.end_time:.1f}s]")
            if seg.summary:
                lines.append(f"摘要: {seg.summary}")
            if seg.events:
                lines.append(f"事件: {', '.join(seg.events[:3])}")
            if seg.entities:
                lines.append(f"实体: {', '.join(seg.entities[:5])}")
            if seg.key_frames:
                lines.append(f"关键画面: {seg.key_frames[0]}")

        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars - 20] + "\n[TRUNCATED]"
        return text

    def to_timeline_data(self) -> List[Dict[str, Any]]:
        """转换为时间轴可视化数据"""
        return [s.to_dict() for s in self.segments]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "max_segments": self.max_segments,
            "count": len(self.segments)
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "长期记忆":
        segments = [语义片段.from_dict(s) for s in d.get("segments", [])]
        return cls(
            segments=segments,
            max_segments=d.get("max_segments", 20)
        )


@dataclass
class Video理解结果:
    """视频理解结果"""
    session_id: str
    video_path: str
    duration: float
    short_term: 短期记忆
    long_term: 长期记忆
    overall_summary: str = ""
    key_events: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    frames_extracted: int = 0
    segments_created: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "duration": self.duration,
            "overall_summary": self.overall_summary,
            "key_events": self.key_events,
            "processing_time": self.processing_time,
            "frames_extracted": self.frames_extracted,
            "segments_created": self.segments_created,
            "short_term": self.short_term.to_dict(),
            "long_term": self.long_term.to_dict()
        }


class 记忆工厂:
    """记忆创建工具"""

    @staticmethod
    def create_frame记忆(
        frame_idx: int,
        timestamp: float,
        caption: str = "",
        audio_text: str = "",
        frame_path: str = ""
    ) -> Frame记忆:
        """创建帧记忆"""
        return Frame记忆(
            frame_idx=frame_idx,
            timestamp=timestamp,
            caption=caption,
            audio_text=audio_text,
            frame_path=frame_path
        )

    @staticmethod
    def create_语义片段(
        start_time: float,
        end_time: float,
        summary: str,
        key_frames: List[str] = None,
        entities: List[str] = None,
        events: List[str] = None
    ) -> 语义片段:
        """创建语义片段"""
        return 语义片段(
            segment_id=str(uuid.uuid4())[:8],
            start_time=start_time,
            end_time=end_time,
            summary=summary,
            key_frames=key_frames or [],
            entities=entities or [],
            events=events or []
        )

    @staticmethod
    def merge_frames_to_segment(
        frames: List[Frame记忆],
        start_time: float,
        end_time: float,
        llm_client
    ) -> 语义片段:
        """将帧列表合并为语义片段（调用LLM生成摘要）"""
        if not frames:
            return 记忆工厂.create_语义片段(start_time, end_time, "无内容")

        # 收集帧描述
        frame_texts = []
        for f in frames:
            parts = []
            if f.caption:
                parts.append(f.caption)
            if f.audio_text:
                parts.append(f"音频: {f.audio_text}")
            if parts:
                frame_texts.append(f"[{f.timestamp:.1f}s] {'; '.join(parts)}")

        if not frame_texts:
            return 记忆工厂.create_语义片段(start_time, end_time, "无有效描述")

        content = "\n".join(frame_texts)
        prompt = f"""请根据以下视频帧描述，生成一个简洁的语义片段摘要：

时间范围: {start_time:.1f}s - {end_time:.1f}s

帧描述:
{content}

请提取:
1. 片段摘要（1-2句话）
2. 关键实体（人物、物体、地点等）
3. 关键事件（动作、发生的事）
4. 最重要的关键帧描述

以JSON格式输出:
{{"summary": "...", "entities": [...], "events": [...], "key_frame": "..."}}"""

        try:
            response = llm_client.chat([
                {"role": "system", "content": "你是视频理解助手，提取关键信息。"},
                {"role": "user", "content": prompt}
            ])
            data = json.loads(response)

            return 记忆工厂.create_语义片段(
                start_time=start_time,
                end_time=end_time,
                summary=data.get("summary", "片段描述"),
                key_frames=[data.get("key_frame", "")] if data.get("key_frame") else [],
                entities=data.get("entities", []),
                events=data.get("events", [])
            )
        except Exception as e:
            # 如果LLM调用失败，使用简单策略
            captions = [f.caption for f in frames if f.caption]
            summary = captions[0][:100] if captions else "片段描述"
            return 记忆工厂.create_语义片段(
                start_time=start_time,
                end_time=end_time,
                summary=summary,
                key_frames=[captions[0]] if captions else [],
                entities=[],
                events=[]
            )
