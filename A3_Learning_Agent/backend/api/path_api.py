import json
import re

from flask import Blueprint, request

from ai.agents import SafetyAgent
from ai.rag import retrieve_knowledge, retrieve_knowledge_items
from ai.llm_api import audit_content, llm_chat
# 兼容下面原来使用的函数名
content_audit = audit_content
spark_chat = llm_chat
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


RESOURCE_TYPE_ORDER = ["doc", "mindmap", "quiz", "code", "video", "reading"]
RESOURCE_TYPE_LABELS = {
    "doc": "讲解文档",
    "quiz": "基础练习题",
    "reading": "拓展阅读",
    "mindmap": "思维导图",
    "code": "代码案例",
    "video": "教学短视频",
}
KNOWN_POINTS = [
    "需求分析", "总体设计", "详细设计", "软件测试", "软件生命周期", "用例图", "类图", "时序图",
    "数据流图", "模块划分", "编码实现", "软件维护", "可行性研究", "软件设计", "调试",
]


def _safe_json(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _clean_text(text: str) -> str:
    return re.sub(r"[#*_`>\-]", "", str(text or "")).strip()


def _section_value(block: str, label: str) -> str:
    match = re.search(rf"\*\*{label}[：:]?\*\*\s*([^\n]+)", block)
    return _clean_text(match.group(1)) if match else ""


def _stage_points(block: str, title: str) -> list[str]:
    hits = [item for item in KNOWN_POINTS if item in block]
    result = []
    for item in hits or [title or "课程核心知识"]:
        if item and item not in result:
            result.append(item)
    return result[:5]


def _stage_duration(block: str, index: int) -> str:
    match = re.search(r"(\d+)\s*天", block)
    return f"预计{match.group(1)}天" if match else f"预计{index + 2}天"


def _parse_path_stages(path_content: str) -> list[dict]:
    content = normalize_markdown(path_content)
    blocks = [item for item in re.split(r"\n(?=##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段))", content) if re.match(r"^##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段)", item.strip())]
    stages = []
    for index, block in enumerate(blocks):
        first_line = block.strip().splitlines()[0] if block.strip() else ""
        title = _clean_text(re.sub(r"^##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段)[：:、.．\s]*", "", first_line)) or f"学习阶段{index + 1}"
        stages.append(
            {
                "index": index + 1,
                "title": title,
                "duration": _stage_duration(block, index),
                "goal": _section_value(block, "目标") or _section_value(block, "学习任务") or "围绕学生画像短板完成本阶段学习任务。",
                "points": _stage_points(block, title),
                "raw": block,
                "status": "pending",
                "resources": [],
            }
        )
    if len(stages) >= 3:
        return stages
    if stages:
        merged_points = []
        for stage in stages:
            for point in stage.get("points") or []:
                if point and point not in merged_points:
                    merged_points.append(point)
        fallback_specs = [
            {"title": "方法关系建构", "duration": "预计3天", "goal": "建立相关方法、流程和阶段之间的关系。", "points": merged_points or ["课程核心知识"]},
            {"title": "练习与实操巩固", "duration": "预计2天", "goal": "通过练习、案例和应用任务完成迁移。", "points": merged_points or ["课程核心知识"]},
        ]
        existing_titles = {stage.get("title") for stage in stages}
        for item in fallback_specs:
            if len(stages) >= 3:
                break
            if item["title"] in existing_titles:
                continue
            next_index = len(stages) + 1
            stages.append({"index": next_index, "raw": "", "status": "pending", "resources": [], **item})
    return stages


def _fallback_stages(resources: list[dict]) -> list[dict]:
    if not resources:
        return []
    return [
        {"index": 1, "title": "基础概念澄清", "duration": "预计2天", "goal": "理解核心概念、阶段产物和输入输出关系。", "points": ["软件生命周期", "需求分析"], "raw": "", "status": "pending", "resources": []},
        {"index": 2, "title": "方法关系建构", "duration": "预计3天", "goal": "建立需求分析、总体设计、详细设计之间的顺序关系。", "points": ["需求分析", "总体设计", "详细设计"], "raw": "", "status": "pending", "resources": []},
        {"index": 3, "title": "练习与实操巩固", "duration": "预计2天", "goal": "通过练习、案例和代码实操完成迁移应用。", "points": ["软件测试", "代码实操"], "raw": "", "status": "pending", "resources": []},
    ]


def _resource_text(resource: dict) -> str:
    return " ".join(
        [
            str(resource.get("title") or ""),
            str(resource.get("resource_type") or ""),
            " ".join(str(item) for item in resource.get("knowledge_points") or []),
            str(resource.get("content") or "")[:500],
        ]
    )


def _resource_score(resource: dict, stage: dict) -> int:
    stage_text = " ".join([stage.get("title", ""), stage.get("goal", ""), " ".join(stage.get("points") or []), stage.get("raw", "")])
    resource_text = _resource_text(resource)
    score = 0
    for point in resource.get("knowledge_points") or []:
        if point and str(point) in stage_text:
            score += 5
    for token in ["需求分析", "总体设计", "详细设计", "测试", "生命周期", "代码", "练习", "用例", "模块"]:
        if token in stage_text and token in resource_text:
            score += 2
    return score


def _resource_order(resource: dict) -> int:
    try:
        return RESOURCE_TYPE_ORDER.index(resource.get("resource_type"))
    except ValueError:
        return 99


def _is_model_error_text(text: str) -> bool:
    content = str(text or "")
    return bool(re.search(r"\{\s*\"?success\"?\s*:\s*false", content, re.IGNORECASE)) or any(
        token in content for token in ["调用失败", "AppIdNoAuthError", "NoAuth", "anthropic/messages"]
    )


def _friendly_resource_content(resource: dict) -> str:
    label = RESOURCE_TYPE_LABELS.get(resource.get("resource_type"), "学习资源")
    points = resource.get("knowledge_points") or ["课程核心知识"]
    return f"# {resource.get('title') or label}\n\n该{label}已挂载到当前学习阶段。请结合本阶段目标，围绕“{'、'.join(str(item) for item in points[:4])}”进行学习。\n\n## 学习建议\n- 先阅读阶段目标与覆盖知识点。\n- 再结合课程知识库配图、案例或练习完成理解。\n- 如需更完整内容，请在修正模型授权后重新生成路径与资源。"


def _normalize_resource(resource: dict) -> dict:
    item = dict(resource)
    item["knowledge_points"] = _safe_json(item.get("knowledge_points"), [])
    if _is_model_error_text(item.get("content")):
        item["content"] = _friendly_resource_content(item)
    item["metadata"] = _safe_json(item.get("metadata"), {})
    stage_meta = item["metadata"].get("stage") if isinstance(item.get("metadata"), dict) else None
    if isinstance(stage_meta, dict):
        item["stage_id"] = item.get("stage_id") or stage_meta.get("stage_id")
        item["stage_index"] = item.get("stage_index") or stage_meta.get("stage_index")
        item["stage_title"] = item.get("stage_title") or stage_meta.get("stage_title")
        item["stage_points"] = item.get("stage_points") or stage_meta.get("stage_points")
    for key in ("stage_id", "stage_index", "stage_title", "stage_points"):
        if not item.get(key) and isinstance(item.get("metadata"), dict):
            item[key] = item["metadata"].get(key)
    item["sources"] = mysql_db.query_all(
        "SELECT source_name AS source, chunk_index, relevance_score AS score, retrieval_mode FROM resource_source WHERE resource_id=%s",
        (item["id"],),
    )
    item["type_label"] = RESOURCE_TYPE_LABELS.get(item.get("resource_type"), item.get("resource_type") or "学习资源")
    return item


def _attach_resources_to_stages(stages: list[dict], resources: list[dict]) -> list[dict]:
    if not stages:
        return stages
    for stage in stages:
        stage["resources"] = []
    if resources:
        assigned_ids = set()
        stage_by_index = {stage.get("index"): stage for stage in stages}
        for resource in sorted(resources, key=_resource_order):
            stage_index = resource.get("stage_index")
            try:
                stage_index = int(stage_index) if stage_index is not None else None
            except Exception:
                stage_index = None
            if stage_index in stage_by_index:
                stage_by_index[stage_index]["resources"].append(resource)
                assigned_ids.add(resource.get("id"))
                continue
            ranked = sorted(
                [(index, stage, _resource_score(resource, stage)) for index, stage in enumerate(stages)],
                key=lambda item: (item[2], -len(item[1].get("resources") or []), -item[0]),
                reverse=True,
            )
            best_index, best_stage, best_score = ranked[0]
            if best_score <= 0:
                best_index = len(assigned_ids) % len(stages)
                best_stage = stages[best_index]
            best_stage["resources"].append(resource)
            assigned_ids.add(resource.get("id"))
        for stage in stages:
            stage["resources"] = sorted(stage["resources"][:6], key=_resource_order)
    for index, stage in enumerate(stages):
        stage["status"] = "current" if index == 0 else "pending"
        stage.pop("raw", None)
    return stages


def _duration_days(duration: str) -> int:
    match = re.search(r"(\d+)", str(duration or ""))
    return int(match.group(1)) if match else 0


def _profile_basis(profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "knowledge_base": profile.get("knowledge_base") or profile.get("knowledge_level") or "待进一步观察",
        "weak_points": profile.get("error_prone_points") or profile.get("weak_points") or "待进一步观察",
        "study_goal": profile.get("study_goal") or "待进一步观察",
        "summary": profile.get("profile_summary") or "本路径基于你的知识基础、薄弱点和学习目标生成。",
    }


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
2. 标题层级必须统一：一级标题用“# 个性化学习路径”，二级标题用“## 阶段一：...”“## 阶段二：...”“## 阶段三：...”，三级标题用“### 学习安排”。
3. 必须生成 3 个学习阶段，不能只生成 1 个阶段；三个阶段应体现“基础理解 → 方法建构 → 练习应用”的递进关系。
4. 每个阶段固定包含五项，且五项名称必须一致：目标、学习任务、推荐资源、练习方式、评估指标。
5. 每个阶段写成短段落和项目符号，不要把所有内容挤在一行。
6. 内容要清楚说明学习顺序、为什么这样学、需要用到哪些文档/题库/视频/案例。
7. 最后添加“## 动态调整建议”和“## 参考依据”两个小节。
8. 只能依据教材原文和学生画像，不要编造不存在的页码、图片和结论。

请严格按这个模板组织，三个阶段都必须保留：

# 个性化学习路径

## 阶段一：基础理解与概念澄清
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

## 阶段二：方法关系与流程建构
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

## 阶段三：案例练习与迁移应用
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


@path_bp.get("/integrated")
@login_required
def integrated_learning_path():
    try:
        session = resolve_profile_session(request.user_id, request.args.to_dict(), create_if_missing=False)
        if not session:
            return success({"topic": "个性化学习路径", "stages": [], "resources": [], "profile_basis": _profile_basis(None)}, "暂无画像会话")
        session_id = session["id"]
        profile = mysql_db.query_one(
            "SELECT * FROM student_profile WHERE user_id=%s AND profile_session_id=%s",
            (request.user_id, session_id),
        )
        path = mysql_db.query_one(
            "SELECT * FROM study_path WHERE user_id=%s AND profile_session_id=%s ORDER BY create_time DESC LIMIT 1",
            (request.user_id, session_id),
        )
        resource_rows = mysql_db.query_all(
            """
            SELECT *
            FROM study_resource
            WHERE user_id=%s AND profile_session_id=%s
            ORDER BY id DESC
            LIMIT 36
            """,
            (request.user_id, session_id),
        )
        resources = [_normalize_resource(item) for item in resource_rows]
        stages = _parse_path_stages(path.get("path_content") if path else "") or _fallback_stages(resources)
        stages = _attach_resources_to_stages(stages, resources)
        total_days = sum(_duration_days(stage.get("duration")) for stage in stages)
        topic = (profile or {}).get("target_course") or (profile or {}).get("study_goal") or (stages[0].get("title") if stages else "个性化学习路径")
        data = {
            "path_id": path.get("id") if path else None,
            "profile_session_id": session_id,
            "topic": topic,
            "total_duration": f"{total_days}天" if total_days else f"{len(stages)}阶段",
            "stage_count": len(stages),
            "resource_count": len(resources),
            "profile_basis": _profile_basis(profile),
            "overview": "以个性化学习路径为主线骨架，将多模态学习资源精准挂载到每个阶段节点。",
            "workflow": [
                {"agent": "PlannerAgent", "role": "读取画像并规划学习阶段、顺序、目标与时长"},
                {"agent": "6类资源生成智能体", "role": "围绕阶段知识点生成文档、题库、阅读、思维导图、代码和视频资源"},
                {"agent": "PackagerAgent", "role": "将资源按知识点和阶段目标匹配挂载到学习节点"},
                {"agent": "EvaluatorAgent", "role": "根据学习反馈和练习结果动态调整后续路径与资源"},
            ],
            "stages": stages,
            "resources": resources,
            "path_content": path.get("path_content") if path else "",
        }
        return success(data, "一体化学习路径查询成功")
    except Exception as exc:
        return fail("一体化学习路径查询失败", 500, {"error": str(exc)})


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



