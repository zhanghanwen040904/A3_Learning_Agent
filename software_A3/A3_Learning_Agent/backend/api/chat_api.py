from flask import Blueprint, request

from ai.rag import retrieve_knowledge
from ai.spark_api import content_audit, see_dance_generate, spark_chat
from utils import fail, require_fields, success
from utils.auth_decorator import login_required

chat_bp = Blueprint("chat", __name__)


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

        evidence = retrieve_knowledge(question, top_k=3)
        prompt = f"""
你是人工智能导论课程智能辅导老师。请严格基于教材原文回答学生问题。
要求：
1. 不得编造教材原文之外的概念；
2. 先给出通俗解释，再给出图解说明的Markdown结构；
3. 最后给出一个小练习帮助学生自测。
学生问题：{question}
教材原文：
{evidence}
""".strip()
        answer_text = spark_chat(prompt)
        if not content_audit(answer_text):
            return fail("答疑内容未通过讯飞内容审核", 403)

        video_url = ""
        if payload.get("need_video", False):
            video_url = see_dance_generate(f"请基于以下答疑内容生成60秒以内教学短视频：{answer_text[:1200]}")

        return success({"answer": answer_text, "diagram": answer_text, "video_url": video_url, "evidence": evidence}, "答疑成功")
    except Exception as exc:
        return fail("智能答疑失败", 500, {"error": str(exc)})


@chat_bp.post("/ask")
@login_required
def ask_alias():
    return answer()
