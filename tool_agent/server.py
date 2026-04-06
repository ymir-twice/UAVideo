import os
import uuid
import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .cache import DiskCache
from .core_llm import CoreLLMClient, now_unix
from .orchestrator import VideoUnderstandingOrchestrator
from .schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseMessage,
)
from .settings import Settings
from .tools.caption import CaptionEngine
from .session import Session


def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "configs", ".env")
    env_path = os.path.abspath(env_path)
    doubao_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pretrained_models", "doubao-1.8"))
    if os.path.exists(doubao_path):
        load_dotenv(doubao_path, override=False)
    if os.path.exists(env_path):
        load_dotenv(env_path, override=False)


def _auth_ok(authorization: str | None, token: str) -> bool:
    if not token:
        return True
    if not authorization:
        return False
    if not authorization.lower().startswith("bearer "):
        return False
    return authorization.split(" ", 1)[1].strip() == token


# SSE事件生成器
async def sse_generator(session_manager, session_id: str):
    """生成SSE流"""
    import time
    last_progress = -1.0

    while True:
        session = session_manager.get_session(session_id)
        if not session:
            yield f"event: error\ndata: Session not found\n\n"
            break

        status = session.status
        if status.progress != last_progress:
            yield f"event: progress\ndata: {status.stage}|{status.progress}|{status.message}\n\n"
            last_progress = status.progress

        if status.stage in ("done", "error"):
            yield f"event: complete\ndata: {status.stage}\n\n"
            break

        await asyncio.sleep(0.5)

    yield f"event: close\ndata:\n\n"


class CreateSessionRequest(BaseModel):
    video_name: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str


def create_app() -> FastAPI:
    _load_env()
    settings = Settings.with_doubao_fallback()
    app = FastAPI(title="Video Understanding Agent API", version="2.0")

    # 初始化组件
    cache = DiskCache(root=Path(settings.cache_dir))
    orchestrator = VideoUnderstandingOrchestrator(settings=settings)
    orchestrator.session_manager.storage_dir = Path(settings.session_storage_dir)

    if settings.caption_enabled:
        orchestrator.captioner = CaptionEngine(
            cache=cache,
            model_name=settings.vllm_caption_model,
            vllm_base_url=settings.vllm_base_url
        )
    if settings.core_llm_base_url and settings.core_llm_api_key and settings.core_llm_model:
        orchestrator.core_llm = CoreLLMClient(
            base_url=settings.core_llm_base_url,
            api_key=settings.core_llm_api_key,
            model=settings.core_llm_model,
            timeout=settings.core_llm_timeout,
        )

    # 进度回调存储
    progress_callbacks: Dict[str, callable] = {}

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"ok": True, "service": "video-understanding-agent", "version": "2.0"}

    # ========== 原有Chat Completions API ==========

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
    @app.post("/chat/completions", response_model=ChatCompletionResponse)
    async def chat_completions(req: ChatCompletionRequest, authorization: str | None = Header(default=None)) -> ChatCompletionResponse:
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        content = await orchestrator.generate(req)
        resp = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            created=now_unix(),
            model="tool-agent",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatCompletionResponseMessage(content=content),
                    finish_reason="stop",
                )
            ],
        )
        return resp

    # ========== 新增Session管理API ==========

    @app.post("/sessions")
    async def create_session(
        video: UploadFile = File(...),
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """创建新Session，上传视频"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        # 保存上传的视频
        video_path = Path(settings.cache_dir) / "uploads" / f"{uuid.uuid4().hex}_{video.filename}"
        video_path.parent.mkdir(parents=True, exist_ok=True)

        with open(video_path, "wb") as f:
            content = await video.read()
            f.write(content)

        # 创建Session
        session = orchestrator.session_manager.create_session(
            video_path=str(video_path),
            video_name=video.filename or "video.mp4"
        )

        return {
            "session_id": session.session_id,
            "video_name": session.video_name,
            "video_path": session.video_path,
            "status": session.status.to_dict(),
            "message": "Session创建成功，请调用 /sessions/{id}/understand 开始处理"
        }

    @app.get("/sessions")
    async def list_sessions(authorization: str | None = Header(default=None)) -> Dict[str, Any]:
        """列出所有Session"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        sessions = orchestrator.session_manager.list_sessions()
        return {"sessions": sessions, "count": len(sessions)}

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: str, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
        """获取Session详情"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "video_name": session.video_name,
            "video_duration": session.video_duration,
            "created_at": session.created_at,
            "status": session.status.to_dict(),
            "total_frames": session.total_frames_processed,
            "total_segments": session.total_segments,
            "has_understanding": session.understanding_result is not None,
            "conversation_count": len(session.conversation_history)
        }

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
        """删除Session"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        success = orchestrator.session_manager.delete_session(session_id)
        return {"success": success, "session_id": session_id}

    @app.post("/sessions/{session_id}/understand")
    async def start_understanding(
        session_id: str,
        background_tasks: BackgroundTasks,
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """触发视频理解流程"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session.is_processing():
            return {
                "message": "视频正在处理中",
                "session_id": session_id,
                "status": session.status.to_dict()
            }

        # 在后台运行理解流程
        async def run_understanding():
            try:
                await orchestrator.understand_video(
                    session.video_path,
                    session_id,
                    max_frames=settings.max_frames
                )
            except Exception as e:
                session = orchestrator.session_manager.get_session(session_id)
                if session:
                    session.update_status("error", message=str(e), error=str(e))
                    orchestrator.session_manager.update_session(session)

        background_tasks.add_task(run_understanding)

        return {
            "message": "视频理解已启动，请通过 /sessions/{id}/stream 监听进度",
            "session_id": session_id
        }

    @app.get("/sessions/{session_id}/stream")
    async def stream_session(
        session_id: str,
        authorization: str | None = Header(default=None),
        token: str | None = Query(default=None, description="SSE auth token (fallback when header unavailable)")
    ):
        """SSE流式输出处理进度"""
        # SSE无法发送自定义header，允许通过query参数传递token
        auth_header = authorization
        if not auth_header and token:
            auth_header = f"Bearer {token}"
        if not _auth_ok(auth_header, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return StreamingResponse(
            sse_generator(orchestrator.session_manager, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    @app.post("/sessions/{session_id}/question")
    async def ask_question(
        session_id: str,
        request: QuestionRequest,
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """基于记忆的问答"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        answer = await orchestrator.answer_question(request.question, session_id)

        return {
            "session_id": session_id,
            "question": request.question,
            "answer": answer,
            "timestamp": now_unix()
        }

    @app.get("/sessions/{session_id}/memory")
    async def get_memory(
        session_id: str,
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """获取记忆可视化数据"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session_id,
            "short_term": session.short_term.to_dict(),
            "long_term": {
                "segments": session.long_term.to_timeline_data(),
                "count": len(session.long_term.segments)
            },
            "video_duration": session.video_duration,
            "frames_summary": session.short_term.get_frames_summary()
        }

    @app.get("/sessions/{session_id}/summary")
    async def get_summary(
        session_id: str,
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """获取视频理解摘要"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.understanding_result:
            return {
                "session_id": session_id,
                "summary": None,
                "message": "视频尚未处理完成"
            }

        result = session.understanding_result
        return {
            "session_id": session_id,
            "summary": result.overall_summary,
            "key_events": result.key_events,
            "duration": result.duration,
            "frames_extracted": result.frames_extracted,
            "segments_created": result.segments_created,
            "processing_time": result.processing_time
        }

    @app.get("/sessions/{session_id}/conversations")
    async def get_conversations(
        session_id: str,
        authorization: str | None = Header(default=None)
    ) -> Dict[str, Any]:
        """获取对话历史"""
        if not _auth_ok(authorization, settings.auth_token):
            raise HTTPException(status_code=401, detail="Unauthorized")

        session = orchestrator.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session_id,
            "conversations": [
                {
                    "question": c.question,
                    "answer": c.answer,
                    "timestamp": c.timestamp,
                    "relevant_segments": c.relevant_segments
                }
                for c in session.conversation_history
            ]
        }

    return app


def main():
    app = create_app()
    settings = Settings.with_doubao_fallback()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
