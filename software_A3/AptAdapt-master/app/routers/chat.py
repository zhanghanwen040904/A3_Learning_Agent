"""对话路由 — 画像抽取 → 知识检索 → LLM 生成（普通 + SSE 流式）

每个阶段独立容错，单阶段失败不阻断后续阶段。
"""
import json
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..llm_client import SparkLLM
from ..services.profile_manager import update_profile_from_conversation
from ..services.retriever import retrieve

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    course: str = "computer_organization"
    chapter: Optional[str] = None


def _build_answer_prompt(message: str, profile: dict, chunks: list[dict]) -> str:
    parts = []

    if profile:
        parts.append(f"学生画像: {json.dumps(profile, ensure_ascii=False)}")

    if chunks:
        sources = "\n".join(
            f"[{c['id']}] {c['title']}: {c['content']}" for c in chunks
        )
        parts.append(f"课程知识库参考片段:\n{sources}")
        parts.append("请基于上述知识库片段回答，如有引用请标注来源 ID。如知识库无法覆盖，请说明「依据不足」。")

    parts.append(f"学生问题: {message}")
    return "\n\n".join(parts)


@router.post("/chat/send", summary="发送消息（普通模式）")
async def send_message(req: ChatRequest, db: Session = Depends(get_db)):
    """
    完整 pipeline: 画像抽取 → 知识检索 → LLM 生成 → 返回。
    每阶段独立容错，pipeline_errors 记录各阶段异常。
    """
    pipeline_errors: list[dict] = []
    profile = None
    chunks: list[dict] = []

    # 1. 画像抽取（可降级）
    try:
        profile = update_profile_from_conversation(db, user_id=1, message=req.message)
    except Exception as e:
        pipeline_errors.append({"stage": "profile", "error": str(e)})

    # 2. 知识库检索（可降级）
    try:
        chunks = retrieve(req.message, top_k=5, course_id=req.course)
    except Exception as e:
        pipeline_errors.append({"stage": "retrieve", "error": str(e)})

    # 3. LLM 生成（不可降级 — 这是核心能力）
    try:
        prompt = _build_answer_prompt(
            req.message,
            profile.model_dump() if profile else None,
            chunks,
        )
        llm = SparkLLM()
        ai_response = llm.chat(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 调用失败: {str(e)}")

    if not ai_response:
        raise HTTPException(status_code=500, detail="AI 没有返回有效内容")

    return {
        "code": 200,
        "message": "success",
        "data": {
            "reply": ai_response,
            "retrieved_chunks": [{"id": c["id"], "title": c["title"]} for c in chunks],
            "pipeline_errors": pipeline_errors or None,
        },
    }


@router.post("/chat/stream", summary="发送消息（SSE 流式模式）")
async def send_message_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """SSE 流式: 画像 → 检索 → 流式生成，每阶段独立容错"""

    def generate():
        pipeline_errors = []
        profile = None
        chunks: list[dict] = []

        # 1. 画像抽取
        yield _sse("agent_status", {"agent": "Profile Agent", "status": "running",
                   "message": "正在分析学习画像..."})
        try:
            profile = update_profile_from_conversation(db, user_id=1, message=req.message)
            yield _sse("agent_status", {"agent": "Profile Agent", "status": "done",
                       "message": "画像更新完成"})
        except Exception as e:
            pipeline_errors.append({"stage": "profile", "error": str(e)})
            yield _sse("agent_status", {"agent": "Profile Agent", "status": "error",
                       "message": f"画像抽取失败: {e}"})

        # 2. 知识库检索
        yield _sse("agent_status", {"agent": "Retriever", "status": "running",
                   "message": "正在检索课程知识库..."})
        try:
            chunks = retrieve(req.message, top_k=5, course_id=req.course)
            chunk_ids = [c["id"] for c in chunks]
            yield _sse("agent_status", {"agent": "Retriever", "status": "done",
                       "message": f"检索到 {len(chunks)} 个相关片段", "chunks": chunk_ids})
        except Exception as e:
            pipeline_errors.append({"stage": "retrieve", "error": str(e)})
            chunk_ids = []
            yield _sse("agent_status", {"agent": "Retriever", "status": "error",
                       "message": f"知识库检索失败: {e}"})

        # 3. 流式生成
        try:
            yield _sse("agent_status", {"agent": "Doc Agent", "status": "running",
                       "message": "正在生成回复..."})
            prompt = _build_answer_prompt(
                req.message,
                profile.model_dump() if profile else None,
                chunks,
            )
            llm = SparkLLM()
            for token in llm.chat_stream(prompt):
                yield _sse("content", {"type": "markdown", "content": token})
            yield _sse("agent_status", {"agent": "Doc Agent", "status": "done"})
            yield _sse("done", {"message": "生成完成", "chunks": chunk_ids,
                       "pipeline_errors": pipeline_errors or None})
        except Exception:
            yield _sse("error", {"message": traceback.format_exc(),
                       "pipeline_errors": pipeline_errors})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"

