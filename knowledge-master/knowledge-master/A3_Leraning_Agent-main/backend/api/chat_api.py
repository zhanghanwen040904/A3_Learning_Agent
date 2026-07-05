import json

from flask import Blueprint, request

from ai.agents import SafetyAgent, TutorAgent
from ai.spark_api import content_audit, see_dance_generate
from db import mysql_db
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

chat_bp = Blueprint("chat", __name__)
tutor_agent = TutorAgent()
safety_agent = SafetyAgent()


def _active_session_id(user_id: int):
    row = mysql_db.query_one(
        "SELECT id FROM profile_session WHERE user_id=%s AND is_active=1 ORDER BY update_time DESC LIMIT 1",
        (user_id,),
    )
    if row:
        return row["id"]
    row = mysql_db.query_one("SELECT id FROM profile_session WHERE user_id=%s ORDER BY update_time DESC LIMIT 1", (user_id,))
    return row["id"] if row else None


@chat_bp.post("/answer")
@login_required
def answer():
    try:
        payload = request.get_json(silent=True) or {}
        ok, field = require_fields(payload, ["question"])
        if not ok:
            return fail(f"缺少必填参数：{field}", 400)

        question = str(payload["question"]).strip()
        if not content_audit(question):
            return fail("问题未通过内容审核", 403)

        session_id = _active_session_id(request.user_id)
        profile = {}
        if session_id:
            profile = mysql_db.query_one(
                "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
                (request.user_id, session_id),
            ) or {}
        result = tutor_agent.answer(question, profile=profile)
        answer_text = result["answer"]
        if not content_audit(answer_text):
            return fail("答疑内容未通过内容审核", 403)

        video_url = ""
        if payload.get("need_video", False):
            video_source = result.get("video_script") or answer_text
            video_url = see_dance_generate(video_source[:1800])

        safety = safety_agent.review(
            "\n".join([answer_text, result.get("diagram", ""), result.get("video_script", "")]),
            result.get("sources", []),
        )

        try:
            mysql_db.insert(
                "learning_event",
                {
                    "user_id": request.user_id,
                    "event_type": "ask_tutor",
                    "knowledge_point": ",".join([str(item.get("metadata", {}).get("title", "")) for item in result.get("sources", [])[:3]]),
                    "detail": json.dumps(
                        {
                    "question": question,
                    "profile_session_id": session_id,
                    "need_video": bool(payload.get("need_video", False)),
                            "source_count": len(result.get("sources", [])),
                            "image_count": len(result.get("images", [])),
                        },
                        ensure_ascii=False,
                    ),
                },
            )
        except Exception:
            pass

        return success(
            {
                "answer": answer_text,
                "diagram": result.get("diagram", ""),
                "video_script": result.get("video_script", ""),
                "video_url": video_url,
                "images": result.get("images", []),
                "image_notes": result.get("image_notes", []),
                "self_check": result.get("self_check", []),
                "next_actions": result.get("next_actions", []),
                "evidence": result.get("evidence", ""),
                "sources": result.get("sources", []),
                "safety": safety,
            },
            "智能辅导成功",
        )
    except Exception as exc:
        return fail("智能辅导失败", 500, {"error": str(exc)})


@chat_bp.post("/ask")
@login_required
def ask_alias():
    return answer()
