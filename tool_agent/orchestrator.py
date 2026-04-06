"""
视频理解编排器

支持长短期记忆管理的视频理解智能体
基于ReAct范式进行推理和工具调用
"""

import base64
import io
import json
import time
import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Callable
from pathlib import Path

from PIL import Image

from .core_llm import CoreLLMClient
from .schemas import ChatCompletionRequest
from .settings import Settings
from .memory import (
    短期记忆, 长期记忆, Frame记忆, 语义片段,
    记忆工厂, Video理解结果
)
from .session import SessionManager, Session, ProcessingStatus
from .tools.caption import CaptionEngine
from .tools.asr import ASREngine, ASRResult

# 日志配置
LOG_DIR = Path("/mnt/data/gk/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
orch_log = LOG_DIR / "orchestrator.log"

def log_orch(session_id: str, msg: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [Orch:{session_id[:8]}] {msg}\n"
    with open(orch_log, "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f"[Orch:{session_id[:8]}] {msg}", flush=True)


ContentPart = Dict[str, Any]
Message = Dict[str, Any]


@dataclass
class 视频处理进度:
    """视频处理进度回调"""
    on_progress: Optional[Callable[[str, float, str], None]] = None

    def report(self, stage: str, progress: float, message: str = ""):
        if self.on_progress:
            self.on_progress(stage, progress, message)


class VideoUnderstandingOrchestrator:
    """
    支持长短期记忆的视频理解编排器

    功能：
    - 自适应视频抽帧
    - 帧级语义生成（caption）
    - ASR音频转写
    - 短期记忆构建与管理
    - 长期记忆提炼与检索
    - 基于记忆的智能问答
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.core_llm: Optional[CoreLLMClient] = None
        self.captioner: Optional[CaptionEngine] = None
        self.asr: Optional[ASREngine] = None
        self.video_extractor = None

        # vLLM客户端（用于本地工具模型）
        self._vllm_caption_client = None
        self._vllm_asr_client = None

        # Session管理
        self.session_manager = SessionManager()

    def _get_vllm_caption_client(self):
        """获取vLLM Caption客户端"""
        if self._vllm_caption_client is None:
            from .tools.vllm_client import VLLMCaptionClient
            self._vllm_caption_client = VLLMCaptionClient()
            self._vllm_caption_client.config.base_url = self.settings.vllm_base_url
            self._vllm_caption_client.config.api_key = self.settings.vllm_api_key
            self._vllm_caption_client.model = self.settings.vllm_caption_model
        return self._vllm_caption_client

    def _get_vllm_asr_client(self):
        """获取vLLM ASR客户端"""
        if self._vllm_asr_client is None:
            from .tools.vllm_client import VLLMASRClient
            self._vllm_asr_client = VLLMASRClient()
            self._vllm_asr_client.config.base_url = self.settings.vllm_base_url
            self._vllm_asr_client.config.api_key = self.settings.vllm_api_key
            self._vllm_asr_client.model = self.settings.vllm_asr_model
        return self._vllm_asr_client

    def initialize_tools(self):
        """初始化工具引擎"""
        from .cache import DiskCache
        from .tools.video import VideoFrameExtractor
        from pathlib import Path

        cache = DiskCache(root=Path(self.settings.cache_dir))

        # 初始化视频帧提取器（带自适应算法）
        if self.video_extractor is None:
            self.video_extractor = VideoFrameExtractor(cache=cache)

        # 初始化Caption引擎（使用vLLM）
        if self.settings.caption_enabled and self.captioner is None:
            self.captioner = CaptionEngine(
                cache=cache,
                model_name=self.settings.vllm_caption_model,
                vllm_base_url=self.settings.vllm_base_url
            )

        # 初始化ASR引擎（使用vLLM）
        if self.settings.asr_enabled and self.asr is None:
            self.asr = ASREngine(
                cache=cache,
                vllm_base_url=self.settings.vllm_base_url,
                model_name=self.settings.vllm_asr_model
            )

        # 初始化核心LLM（豆包 - 仅用于语言推理）
        if self.core_llm is None and self.settings.core_llm_base_url:
            self.core_llm = CoreLLMClient(
                base_url=self.settings.core_llm_base_url,
                api_key=self.settings.core_llm_api_key,
                model=self.settings.core_llm_model,
                timeout=self.settings.core_llm_timeout,
            )

    # ==================== 输入解析 ====================

    def extract_inputs(self, messages: List[Message]) -> Tuple[str, List[ContentPart]]:
        """解析用户消息，提取问题和媒体部分"""
        user_text_parts: List[str] = []
        media_parts: List[ContentPart] = []
        for m in messages:
            if m.get("role") != "user":
                continue
            content = m.get("content")
            if isinstance(content, str):
                user_text_parts.append(content)
                continue
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    t = part.get("type")
                    if t == "text" and isinstance(part.get("text"), str):
                        user_text_parts.append(part["text"])
                    elif t in {"image_url", "video_path"}:
                        media_parts.append(part)
                    elif t == "video":
                        # 处理视频类型
                        video_val = part.get("video", "")
                        if isinstance(video_val, str):
                            media_parts.append({"type": "video_path", "video_path": video_val})
        question = "\n".join([x for x in user_text_parts if x.strip()]).strip()
        return question, media_parts

    def _decode_image_url(self, url: str) -> Optional[bytes]:
        """解码图片URL为字节数据"""
        u = url.strip()
        if u.startswith("data:image/") and "base64," in u:
            b64 = u.split("base64,", 1)[1]
            return base64.b64decode(b64)
        if u.startswith("file://"):
            path = u[len("file://"):]
            with open(path, "rb") as f:
                return f.read()
        if u.startswith("/"):
            with open(u, "rb") as f:
                return f.read()
        return None

    def _sample(self, items: List[Any], max_n: int) -> List[Any]:
        """均匀采样"""
        if len(items) <= max_n:
            return items
        if max_n <= 1:
            return [items[0]]
        idxs = [round(i * (len(items) - 1) / (max_n - 1)) for i in range(max_n)]
        return [items[i] for i in idxs]

    # ==================== 视频理解流程 ====================

    async def understand_video(
        self,
        video_path: str,
        session_id: str,
        max_frames: int = 16,
        progress_callback: Optional[Callable[[str, float, str], None]] = None
    ) -> Video理解结果:
        """
        完整视频理解流程

        步骤：
        1. 获取视频信息
        2. 自适应抽帧
        3. 并行caption + OCR
        4. ASR音频转写
        5. 构建短期记忆
        6. 定期consolidate到长期记忆
        7. 生成整体摘要
        """
        log_orch(session_id, f"Starting understand_video, video_path={video_path}, max_frames={max_frames}")

        self.initialize_tools()
        log_orch(session_id, "Tools initialized")

        session = self.session_manager.get_session(session_id)
        if not session:
            log_orch(session_id, "ERROR: Session not found!")
            raise ValueError(f"Session {session_id} not found")

        start_time = time.time()

        # 更新状态：开始处理
        session.update_status("extracting", progress=0.1, message="正在提取视频帧...")
        self.session_manager.update_session(session)
        log_orch(session_id, "Status set to extracting")

        try:
            # Step 1: 获取视频信息
            log_orch(session_id, "Step 1: Getting video duration")
            duration = self._get_video_duration(video_path)
            session.video_duration = duration
            session.update_status("extracting", progress=0.15, message=f"视频时长: {duration:.1f}秒")
            self.session_manager.update_session(session)
            log_orch(session_id, f"Duration: {duration:.1f}s")

            # Step 2: 提取帧
            log_orch(session_id, f"Step 2: Extracting frames (max={max_frames})")
            frames = self._extract_frames(video_path, max_frames)
            session.total_frames_processed = len(frames)
            session.update_status("captioning", progress=0.3, message=f"已提取 {len(frames)} 帧")
            self.session_manager.update_session(session)
            log_orch(session_id, f"Extracted {len(frames)} frames")

            # Step 3: 处理每帧（caption）
            log_orch(session_id, "Step 3: Processing frames (caption)")
            short_term = 短期记忆(window_size=50, max_age_seconds=300)
            asr_result = None

            for i, (frame_path, timestamp) in enumerate(frames):
                log_orch(session_id, f"  Processing frame {i+1}/{len(frames)}: {frame_path}")
                frame_data = await self._process_frame(
                    frame_path, timestamp, i,
                    session_id=session_id
                )
                short_term.add(frame_data)

                progress = 0.3 + (0.4 * (i + 1) / len(frames))
                session.update_status("captioning", progress=progress,
                                   current_frame=i+1, total_frames=len(frames))
                self.session_manager.update_session(session)

                if progress_callback:
                    progress_callback("captioning", progress, f"处理帧 {i+1}/{len(frames)}")

            log_orch(session_id, f"Step 3 complete: {len(short_term.frames)} frames processed")

            # Step 4: ASR音频转写
            if self.asr and duration > 0:
                log_orch(session_id, "Step 4: ASR audio transcription")
                session.update_status("asr", progress=0.7, message="正在转写音频...")
                self.session_manager.update_session(session)

                try:
                    asr_result = self.asr.transcribe_video(video_path)
                    # 将ASR结果同步到帧
                    for frame in short_term.frames:
                        frame.audio_text = asr_result.get_text_at_time(frame.timestamp)
                    log_orch(session_id, "ASR completed")
                except Exception as e:
                    log_orch(session_id, f"ASR error (skipping): {str(e)[:100]}")
                    session.update_status("asr", progress=0.7, message=f"ASR跳过: {str(e)[:50]}")

                if progress_callback:
                    progress_callback("asr", 0.8, "音频转写完成")
            else:
                log_orch(session_id, "Step 4 skipped: no ASR available or duration=0")

            # Step 5: 保存短期记忆
            log_orch(session_id, "Step 5: Saving short-term memory")
            session.short_term = short_term
            session.update_status("consolidating", progress=0.85, message="构建长期记忆...")
            self.session_manager.update_session(session)

            # Step 6: Consolidate到长期记忆
            log_orch(session_id, "Step 6: Consolidating to long-term memory")
            long_term = await self._consolidate_to_long_term(
                session_id, short_term, session
            )
            session.long_term = long_term
            session.total_segments = len(long_term.segments)

            if progress_callback:
                progress_callback("consolidating", 0.95, "记忆构建完成")

            # Step 7: 生成整体摘要
            overall_summary = await self._generate_overall_summary(session)

            # 完成
            processing_time = time.time() - start_time
            session.update_status("done", progress=1.0, message="处理完成")
            self.session_manager.update_session(session)

            result = Video理解结果(
                session_id=session_id,
                video_path=video_path,
                duration=duration,
                short_term=short_term,
                long_term=long_term,
                overall_summary=overall_summary,
                key_events=[s.summary for s in long_term.segments[:5]],
                processing_time=processing_time,
                frames_extracted=len(frames),
                segments_created=len(long_term.segments)
            )
            session.understanding_result = result
            self.session_manager.update_session(session)

            log_orch(session_id, f"COMPLETED in {processing_time:.1f}s")
            log_orch(session_id, f"  frames: {len(frames)}, segments: {len(long_term.segments)}")
            return result

        except Exception as e:
            import traceback
            log_orch(session_id, f"ERROR: {type(e).__name__}: {str(e)}")
            log_orch(session_id, f"Traceback: {traceback.format_exc()}")
            session.update_status("error", progress=0.0, message=str(e), error=str(e))
            self.session_manager.update_session(session)
            raise

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        import subprocess
        import json

        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "json", video_path
        ]
        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            data = json.loads(result.stdout.decode("utf-8"))
            return float(data["format"]["duration"])
        except:
            return 0.0

    def _extract_frames(self, video_path: str, max_frames: int) -> List[Tuple[str, float]]:
        """提取视频帧，返回 (帧路径, 时间戳) 列表

        使用自适应抽帧算法：
        - 基于颜色直方图计算帧间差异
        - 变化超过阈值时保留该帧
        - 保证最少8帧，最多max_frames
        """
        if self.video_extractor is None:
            self.initialize_tools()

        try:
            # 使用自适应抽帧
            frames = self.video_extractor.extract_adaptive(
                video_path,
                min_frames=8,
                max_frames=max_frames,
                threshold=self.settings.adaptive_threshold
            )
            return frames
        except Exception:
            # 回退到均匀抽帧
            frames = self.video_extractor.extract_uniform(video_path, n_frames=max_frames)
            return [(f, i * len(frames) / max_frames) for i, f in enumerate(frames)]

    async def _process_frame(
        self,
        frame_path: str,
        timestamp: float,
        frame_idx: int,
        session_id: str = ""
    ) -> Frame记忆:
        """处理单帧：caption"""
        frame记忆 = Frame记忆(
            frame_idx=frame_idx,
            timestamp=timestamp,
            frame_path=frame_path
        )

        # 读取图片
        try:
            with open(frame_path, 'rb') as f:
                img_bytes = f.read()
            img = Image.open(frame_path).convert("RGB")
        except Exception:
            return frame记忆

        # Caption
        if self.captioner:
            try:
                caption = self.captioner.caption(image_bytes=img_bytes, image=img)
                frame记忆.caption = caption
            except Exception:
                pass

        return frame记忆

    async def _consolidate_to_long_term(
        self,
        session_id: str,
        short_term: 短期记忆,
        session: Session
    ) -> 长期记忆:
        """将短期记忆提炼为长期记忆的语义片段"""
        long_term = 长期记忆(max_segments=20)

        if not short_term.frames:
            return long_term

        # 按时间分组成片段（每30秒一组）
        group_duration = 30.0  # 每组30秒
        groups: Dict[int, List[Frame记忆]] = {}

        for frame in short_term.frames:
            group_idx = int(frame.timestamp / group_duration)
            if group_idx not in groups:
                groups[group_idx] = []
            groups[group_idx].append(frame)

        # 为每组生成语义片段
        for group_idx in sorted(groups.keys()):
            group_frames = groups[group_idx]
            if not group_frames:
                continue

            start_time = group_frames[0].timestamp
            end_time = group_frames[-1].timestamp

            # 使用LLM生成片段摘要
            if self.core_llm and len(group_frames) > 0:
                try:
                    segment = 记忆工厂.merge_frames_to_segment(
                        group_frames, start_time, end_time, self.core_llm
                    )
                    segment.importance_score = len(group_frames) / len(short_term.frames)
                    long_term.add_segment(segment)
                except Exception:
                    # 降级处理
                    captions = [f.caption for f in group_frames if f.caption]
                    summary = captions[0][:100] if captions else f"{start_time:.0f}s-{end_time:.0f}s内容"
                    segment = 语义片段(
                        segment_id=f"seg_{group_idx}",
                        start_time=start_time,
                        end_time=end_time,
                        summary=summary,
                        key_frames=captions[:3] if captions else []
                    )
                    long_term.add_segment(segment)
            else:
                # 无LLM时使用简单策略
                captions = [f.caption for f in group_frames if f.caption]
                summary = "; ".join(captions[:2]) if captions else f"{start_time:.0f}s-{end_time:.0f}s"
                segment = 语义片段(
                    segment_id=f"seg_{group_idx}",
                    start_time=start_time,
                    end_time=end_time,
                    summary=summary[:200],
                    key_frames=captions[:3] if captions else []
                )
                long_term.add_segment(segment)

        return long_term

    async def _generate_overall_summary(self, session: Session) -> str:
        """生成视频整体摘要"""
        if not self.core_llm:
            return session.long_term.segments[0].summary if session.long_term.segments else "无摘要"

        # 构建上下文
        segment_summaries = []
        for seg in session.long_term.segments:
            segment_summaries.append(f"[{seg.start_time:.0f}s-{seg.end_time:.0f}s] {seg.summary}")

        if not segment_summaries:
            return "无法生成摘要"

        content = "\n".join(segment_summaries)
        prompt = f"""请根据以下视频片段摘要，生成一段整体概述：

视频时长: {session.video_duration:.1f}秒
片段数量: {len(segment_summaries)}

片段摘要:
{content}

请生成一段2-3句话的视频整体概述，简明扼要地描述视频的主要内容。"""

        try:
            response = self.core_llm.chat([
                {"role": "system", "content": "你是视频理解助手，生成简洁准确的摘要。"},
                {"role": "user", "content": prompt}
            ])
            return response.strip()
        except Exception:
            return segment_summaries[0][:200] if segment_summaries else "无摘要"

    # ==================== 问答流程 ====================

    async def answer_question(self, question: str, session_id: str) -> str:
        """基于记忆的智能问答"""
        self.initialize_tools()

        session = self.session_manager.get_session(session_id)
        if not session:
            return "错误：Session不存在"

        if not session.short_term.frames and not session.long_term.segments:
            return "错误：视频尚未处理完成，请先调用 /understand 接口"

        # 构建上下文
        context_parts = []

        # 1. 视频整体摘要
        if session.understanding_result and session.understanding_result.overall_summary:
            context_parts.append(f"【视频概述】\n{session.understanding_result.overall_summary}")

        # 2. 长期记忆中的相关片段
        if session.long_term.segments:
            relevant_segments = session.long_term.get_relevant(question, top_k=5)
            if relevant_segments:
                seg_texts = []
                for seg in relevant_segments:
                    parts = [f"[{seg.start_time:.0f}s-{seg.end_time:.0f}s] {seg.summary}"]
                    if seg.events:
                        parts.append(f"事件: {', '.join(seg.events[:2])}")
                    if seg.entities:
                        parts.append(f"实体: {', '.join(seg.entities[:3])}")
                    seg_texts.append("\n".join(parts))
                context_parts.append(f"【相关记忆片段】\n" + "\n---\n".join(seg_texts))

        # 3. 最近的短期记忆
        if session.short_term.frames:
            recent_frames = session.short_term.get_recent(5)
            frame_texts = []
            for f in recent_frames:
                parts = []
                if f.caption:
                    parts.append(f"画面: {f.caption}")
                if f.audio_text:
                    parts.append(f"音频: {f.audio_text}")
                if parts:
                    frame_texts.append(f"[{f.timestamp:.1f}s] {'; '.join(parts)}")
            if frame_texts:
                context_parts.append(f"【最近画面】\n" + "\n".join(frame_texts))

        context = "\n\n".join(context_parts)

        # 构建video_info
        if session.understanding_result:
            video_info_str = f"视频时长: {session.video_duration:.1f}秒\n总帧数: {session.total_frames_processed}"
        else:
            video_info_str = "视频尚未处理完成"

        # 构建prompt
        prompt = f"""视频问答任务。请根据提供的视频记忆信息回答用户问题。

如果记忆信息不足以回答问题，请说明"根据视频内容无法确定"，不要编造答案。

{video_info_str}

{context}

用户问题: {question}

请给出准确、简洁的回答："""

        try:
            answer = self.core_llm.chat([
                {"role": "system", "content": "你是专业的视频理解助手，根据提供的记忆信息准确回答问题。"},
                {"role": "user", "content": prompt}
            ])

            # 记录对话
            relevant_seg_ids = [s.segment_id for s in session.long_term.get_relevant(question, top_k=3)]
            session.add_conversation(question, answer, relevant_seg_ids)
            self.session_manager.update_session(session)

            return answer.strip()

        except Exception as e:
            return f"抱歉，回答时出现错误: {str(e)}"

    # ==================== 简单API兼容 ====================

    async def generate(self, req: ChatCompletionRequest) -> str:
        """简单的generate接口，兼容现有API"""
        messages = [m.model_dump() for m in req.messages]
        question, media_parts = self.extract_inputs(messages)

        if not question:
            question = "描述这个视频的内容"

        if not media_parts:
            # 纯文本问答
            if self.core_llm:
                return self.core_llm.chat(messages)
            return "CORE_LLM is not configured."

        # 视频/图像处理
        images = []
        for part in media_parts:
            if part.get("type") == "image_url":
                image_url = part.get("image_url") or {}
                url = image_url.get("url")
                if isinstance(url, str):
                    b = self._decode_image_url(url)
                    if b:
                        images.append(b)
            elif part.get("type") == "video_path":
                video_path = part.get("video_path", "")
                if video_path:
                    frames = self._extract_frames(video_path, self.settings.max_frames)
                    for frame_path, timestamp in frames:
                        try:
                            with open(frame_path, 'rb') as f:
                                images.append(f.read())
                        except:
                            pass

        if not images:
            if self.core_llm:
                return self.core_llm.chat(messages)
            return "No valid media found."

        # 采样图片
        images = self._sample(images, self.settings.max_frames)

        # 处理图片
        captions = []

        for b in images:
            try:
                img = Image.open(io.BytesIO(b)).convert("RGB")
            except Exception:
                continue

            if self.captioner:
                try:
                    c = self.captioner.caption(image_bytes=b, image=img)
                    if isinstance(c, str) and c.strip():
                        captions.append(c.strip())
                except Exception:
                    pass

        # 构建证据
        evidence_parts = []
        if captions:
            evidence_parts.append("CAPTIONS:\n" + "\n".join(captions))

        evidence_text = "\n\n".join(evidence_parts)
        if len(evidence_text) > self.settings.max_evidence_chars:
            evidence_text = evidence_text[:self.settings.max_evidence_chars - 20] + "\n[TRUNCATED]"

        # 构建消息
        if evidence_text:
            user_msg = f"{question}\n\nVISUAL EVIDENCE:\n{evidence_text}\n\nFinal answer:"
        else:
            user_msg = question

        llm_messages = [
            {"role": "system", "content": "You are a benchmark assistant. Use the provided visual evidence to answer. Output the final answer only, without extra explanation unless explicitly requested."},
            {"role": "user", "content": user_msg}
        ]

        if self.core_llm:
            return self.core_llm.chat(llm_messages, temperature=req.temperature, max_tokens=req.max_tokens)
        return "CORE_LLM is not configured."
