"""
Session管理系统

管理用户会话状态，包含视频信息、记忆状态和对话历史
"""

import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path
import threading

from .memory import 短期记忆, 长期记忆, Video理解结果, Frame记忆, 语义片段


@dataclass
class 对话记录:
    """单轮对话记录"""
    question: str
    answer: str
    timestamp: float
    relevant_segments: List[str] = field(default_factory=list)  # 涉及的语义片段ID

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "对话记录":
        return cls(**d)


@dataclass
class ProcessingStatus:
    """处理状态"""
    stage: str = "idle"  # idle, uploading, extracting, captioning, asr, consolidating, done, error
    progress: float = 0.0  # 0.0 - 1.0
    message: str = ""
    current_frame: int = 0
    total_frames: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "error": self.error
        }


@dataclass
class Session:
    """用户会话"""
    session_id: str
    video_path: str
    video_name: str
    video_duration: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: ProcessingStatus = field(default_factory=ProcessingStatus)

    # 记忆
    short_term: 短期记忆 = field(default_factory=短期记忆)
    long_term: 长期记忆 = field(default_factory=长期记忆)

    # 视频理解结果
    understanding_result: Optional[Video理解结果] = None

    # 对话历史
    conversation_history: List[对话记录] = field(default_factory=list)

    # 处理统计
    total_frames_processed: int = 0
    total_segments: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "video_path": self.video_path,
            "video_name": self.video_name,
            "video_duration": self.video_duration,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.to_dict(),
            "short_term": self.short_term.to_dict(),
            "long_term": self.long_term.to_dict(),
            "understanding_result": self.understanding_result.to_dict() if self.understanding_result else None,
            "conversation_history": [c.to_dict() for c in self.conversation_history],
            "total_frames_processed": self.total_frames_processed,
            "total_segments": self.total_segments
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        status = ProcessingStatus(**d.get("status", {}))
        short_term = 短期记忆.from_dict(d.get("short_term", {}))
        long_term = 长期记忆.from_dict(d.get("long_term", {}))
        understanding = None
        if d.get("understanding_result"):
            ir = d["understanding_result"]
            understanding = Video理解结果(
                session_id=ir["session_id"],
                video_path=ir["video_path"],
                duration=ir["duration"],
                short_term=短期记忆.from_dict(ir["short_term"]),
                long_term=长期记忆.from_dict(ir["long_term"]),
                overall_summary=ir.get("overall_summary", ""),
                key_events=ir.get("key_events", []),
                processing_time=ir.get("processing_time", 0.0),
                frames_extracted=ir.get("frames_extracted", 0),
                segments_created=ir.get("segments_created", 0)
            )
        conversation = [对话记录.from_dict(c) for c in d.get("conversation_history", [])]

        return cls(
            session_id=d["session_id"],
            video_path=d["video_path"],
            video_name=d["video_name"],
            video_duration=d.get("video_duration", 0.0),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            status=status,
            short_term=short_term,
            long_term=long_term,
            understanding_result=understanding,
            conversation_history=conversation,
            total_frames_processed=d.get("total_frames_processed", 0),
            total_segments=d.get("total_segments", 0)
        )

    def add_conversation(self, question: str, answer: str, relevant_segments: List[str] = None):
        """添加对话记录"""
        self.conversation_history.append(对话记录(
            question=question,
            answer=answer,
            timestamp=time.time(),
            relevant_segments=relevant_segments or []
        ))
        self.updated_at = time.time()

    def update_status(self, stage: str, progress: float = None, message: str = "", **kwargs):
        """更新处理状态"""
        self.status.stage = stage
        if progress is not None:
            self.status.progress = progress
        if message:
            self.status.message = message
        for k, v in kwargs.items():
            if hasattr(self.status, k):
                setattr(self.status, k, v)
        self.updated_at = time.time()

    def is_processing(self) -> bool:
        """是否正在处理"""
        return self.status.stage not in ("idle", "done", "error")


class SessionManager:
    """Session管理器"""

    def __init__(self, storage_dir: str = "/mnt/data/gk/.cache/tool_agent/sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()

    def create_session(self, video_path: str, video_name: str = None, video_duration: float = 0.0) -> Session:
        """创建新session"""
        session_id = str(uuid.uuid4())[:12]

        if video_name is None:
            video_name = Path(video_path).name

        session = Session(
            session_id=session_id,
            video_path=video_path,
            video_name=video_name,
            video_duration=video_duration,
            status=ProcessingStatus(stage="idle", progress=0.0, message="准备就绪")
        )

        with self.lock:
            self.sessions[session_id] = session

        # 保存到磁盘
        self._save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """获取session"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session is None:
                # 尝试从磁盘加载
                session = self._load_session(session_id)
                if session:
                    self.sessions[session_id] = session
            return session

    def update_session(self, session: Session):
        """更新session"""
        with self.lock:
            session.updated_at = time.time()
            self.sessions[session.session_id] = session
        self._save_session(session)

    def delete_session(self, session_id: str) -> bool:
        """删除session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]

        # 删除磁盘文件
        session_file = self.storage_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()

        # 删除视频文件（如果存在）
        session = self.get_session(session_id)
        if session and Path(session.video_path).exists():
            try:
                Path(session.video_path).unlink()
            except:
                pass

        return True

    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有session摘要"""
        with self.lock:
            return [
                {
                    "session_id": s.session_id,
                    "video_name": s.video_name,
                    "created_at": s.created_at,
                    "status": s.status.to_dict()
                }
                for s in self.sessions.values()
            ]

    def _save_session(self, session: Session):
        """保存session到磁盘"""
        session_file = self.storage_dir / f"{session.session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_session(self, session_id: str) -> Optional[Session]:
        """从磁盘加载session"""
        session_file = self.storage_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception:
            return None

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """清理过旧的session"""
        cutoff = time.time() - max_age_hours * 3600
        with self.lock:
            to_delete = [
                sid for sid, s in self.sessions.items()
                if s.updated_at < cutoff
            ]
            for sid in to_delete:
                del self.sessions[sid]

        # 清理磁盘
        for session_file in self.storage_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                if data.get("updated_at", 0) < cutoff:
                    session_file.unlink()
            except:
                pass
