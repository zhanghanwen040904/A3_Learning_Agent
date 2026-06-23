import json
import re

from flask import Blueprint, request

from ai.agents import SafetyAgent
from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.spark_api import content_audit, spark_chat
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

path_bp = Blueprint("path", __name__)
safety_agent = SafetyAgent()


def normalize_markdown(text: str) -> str:
    content = str(text or "").strip()
    fenced = re.fullmatch(r"```(?:markdown|md|text)?\s*([\s\S]*?)\s*```", content, flags=re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = re.sub(r"^\s*```(?:markdown|md|text)?\s*$", "", content, flags=re.IGNORECASE | re.MULTILINE)
    content = re.sub(r"^\s*```\s*$", "", content, flags=re.MULTILINE)
    content = "\n".join(line[4:] if line.startswith("    ") and not line.startswith("        ") else line for line in content.splitlines())
    content = re.sub(r"^\s*[-*]\s*\*\*(目标|学习任务|推荐资源|练习方式|评估指标)\*\*\s*[:：]", r"**\1：**", content, flags=re.MULTILINE)
    return content.strip()


@path_bp.post("/generate")
@login_required
def generate_learning_path():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = request.user_id
        session = resolve_profile_session(user_id, payload, create_if_missing=False)
        if not session:
            return fail("未找到画像会话，无法生成学习路径", 404)
        session_id = session["id"]
        profile = payload.get("profile") or mysql_db.query_one("SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s", (user_id, session_id))
        if not profile:
            return fail("未找到学生画像，无法生成学习路径", 404)

        profile_text = json.dumps(profile, ensure_ascii=False, default=str)
        if not content_audit(profile_text):
            return fail("画像内容未通过讯飞内容审核", 403)

        query = str(profile.get("weak_points") or profile.get("study_goal") or "软件工程")
        knowledge = retrieve_knowledge(query, top_k=3)
        sources = retrieve_knowledge_items(query, top_k=3)
        prompt = f"""
你是软件工程课程学习规划师。请基于学生画像和教材原文生成个性化学习路径。

输出要求：
1. 只输出普通 Markdown 正文，不要代码围栏，不要 JSON，不要 ASCII 图，不要复杂表格，不要 emoji。
2. 标题层级必须统一：一级标题用“# 个性化学习路径”，二级标题用“## 阶段一：...”，三级标题用“### 学习安排”。
3. 每个阶段固定包含五项，且五项名称必须一致：目标、学习任务、推荐资源、练习方式、评估指标。
4. 每个阶段写成短段落和项目符号，不要把所有内容挤在一行。
5. 内容要清楚说明学习顺序、为什么这样学、需要用到哪些文档/题库/视频/案例。
6. 最后添加“## 动态调整建议”和“## 参考依据”两个小节。
7. 只能依据教材原文和学生画像，不要编造不存在的页码、图片和结论。

请严格按这个模板组织：

# 个性化学习路径

## 阶段一：阶段名称
### 学习安排
**目标：** ...
**学习任务：**
- ...
**推荐资源：**
- ...
**练习方式：**
- ...
**评估指标：**
- ...

学生画像：
{profile_text}

教材原文：
{knowledge}
""".strip()
        path_content = normalize_markdown(spark_chat(prompt))
        if not content_audit(path_content):
            return fail("生成的学习路径未通过讯飞内容审核", 403)

        safety = safety_agent.review(path_content, sources)
        path_id = mysql_db.insert("study_path", {"user_id": user_id, "profile_session_id": session_id, "path_content": path_content, "status": "active"})
        return success({"id": path_id, "user_id": user_id, "profile_session_id": session_id, "path_content": path_content, "status": "active", "sources": sources, "safety": safety}, "学习路径生成成功")
    except Exception as exc:
        return fail("学习路径生成失败", 500, {"error": str(exc)})


@path_bp.get("/")
@login_required
def list_my_paths():
    try:
        session = resolve_profile_session(request.user_id, create_if_missing=False)
        if not session:
            return success([], "暂无画像会话学习路径")
        paths = mysql_db.query_all("SELECT * FROM study_path WHERE user_id=%s AND profile_session_id=%s ORDER BY create_time DESC", (request.user_id, session["id"]))
        return success(paths, "查询成功")
    except Exception as exc:
        return fail("学习路径查询失败", 500, {"error": str(exc)})


@path_bp.get("/<int:user_id>")
@login_required
def list_paths(user_id: int):
    return list_my_paths()
