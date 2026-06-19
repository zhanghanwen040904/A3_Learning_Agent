from flask import Blueprint, request

from ai.agents import SafetyAgent, TutorAgent
from ai.spark_api import content_audit, see_dance_generate
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

chat_bp = Blueprint("chat", __name__)
tutor_agent = TutorAgent()
safety_agent = SafetyAgent()


@chat_bp.post("/answer")
@login_required
def answer():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        question = str(payload["question"])
        if not content_audit(question):
            return fail("问题未通过讯飞内容审核", 403)

        result = tutor_agent.answer(question)
        answer_text = result["answer"]
        if not content_audit(answer_text):
            return fail("答疑内容未通过讯飞内容审核", 403)

        video_url = ""
        if payload.get("need_video", False):
            video_url = see_dance_generate(f"请基于以下答疑内容生成60秒以内教学短视频：{answer_text[:1200]}")

        safety = safety_agent.review(answer_text, result.get("sources", []))
        return success(
            {
                "answer": answer_text,
                "diagram": answer_text,
                "video_url": video_url,
                "evidence": result.get("evidence", ""),
                "sources": result.get("sources", []),
                "safety": safety,
            },
            "答疑成功",
        )
    except Exception as exc:
        return fail("智能答疑失败", 500, {"error": str(exc)})


@chat_bp.post("/ask")
@login_required
def ask_alias():
    return answer()
