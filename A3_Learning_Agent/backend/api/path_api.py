import json
import logging
import re

from flask import Blueprint, request

from ai.agents import SafetyAgent
from ai.rag import format_knowledge_items, retrieve_knowledge, retrieve_knowledge_items, select_profile_knowledge_items
from ai.llm_api import audit_content, llm_chat
# 兼容下面原来使用的函数名
content_audit = audit_content
spark_chat = llm_chat
from db import mysql_db
from utils import fail, success
from utils.auth_decorator import login_required
from utils.profile_session import resolve_profile_session

path_bp = Blueprint("path", __name__)
logger = logging.getLogger(__name__)
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
    "问题定义", "可行性研究", "需求分析", "需求规格", "总体设计", "详细设计", "软件设计", "编码实现", "调试",
    "软件测试", "软件维护", "软件生命周期", "瀑布模型", "用例图", "类图", "时序图", "数据流图", "模块划分",
    "阶段衔接", "阶段边界", "阶段产物", "输入输出", "流程建构", "产物驱动", "质量闭环", "案例应用", "迁移应用",
]
LIFECYCLE_STAGE_POINTS = ["问题定义", "可行性研究", "需求分析", "软件设计", "编码实现", "软件测试", "软件维护"]
STAGE_NAMES = ["一", "二", "三", "四", "五"]


def _profile_points(profile: dict, payload: dict | None = None) -> list[str]:
    payload = payload or {}
    text = " ".join(
        str(item or "")
        for item in [
            payload.get("learning_need"),
            payload.get("adjustment"),
            profile.get("error_prone_points"),
            profile.get("weak_points"),
            profile.get("study_goal"),
            profile.get("current_topic"),
        ]
    )
    points = [item for item in KNOWN_POINTS if item in text]
    if not points:
        points = ["软件生命周期", "可行性研究", "需求分析"]
    result = []
    for point in points:
        if point and point not in result:
            result.append(point)
    return result[:6]


def _unique_points(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _chunk_points(points: list[str], chunk_size: int) -> list[list[str]]:
    values = _unique_points(points)
    if not values:
        return []
    return [values[index:index + chunk_size] for index in range(0, len(values), chunk_size)]


def _recommended_resources(points: list[str], is_last: bool = False) -> str:
    items = ["讲解文档", "阶段知识导图", "教学短视频", "拓展阅读"]
    if any(point in {"编码实现", "软件测试", "详细设计", "总体设计"} for point in points):
        items.insert(2, "代码案例")
    if is_last:
        items.append("阶段测评")
    return "、".join(_unique_points(items))


def _render_stage(index: int, title: str, goal: str, tasks: list[str], points: list[str], practice: list[str], metrics: list[str]) -> str:
    phase = STAGE_NAMES[index] if index < len(STAGE_NAMES) else str(index + 1)
    return "\n".join(
        [
            f"## 阶段{phase}：{title}",
            "### 学习安排",
            f"**目标：** {goal}",
            "**学习任务：**",
            *[f"- {item}" for item in tasks],
            "**推荐资源：**",
            f"- {_recommended_resources(points, is_last=index >= 2)}。",
            "**练习方式：**",
            *[f"- {item}" for item in practice],
            "**评估指标：**",
            *[f"- {item}" for item in metrics],
        ]
    )


def _build_dynamic_lifecycle_stages(goal: str, lifecycle_points: list[str]) -> list[str]:
    point_chunks = _chunk_points(lifecycle_points[1:] if lifecycle_points[:1] == ["软件生命周期"] else lifecycle_points, 2)
    titles = [
        ("软件生命周期总览与阶段认知", "先建立“为什么要分阶段”的整体认识，理解软件生命周期覆盖软件从提出问题到维护演进的全过程。"),
        ("前期阶段边界与输入输出", "分清生命周期前期阶段各自解决什么问题，避免把阶段目标、任务和产物混在一起。"),
        ("开发实施与质量闭环", "理解设计、编码、测试、维护如何衔接，形成对开发闭环和返工风险的整体判断。"),
        ("案例判断与阶段迁移应用", "把阶段知识放到真实项目案例中，能够判断当前所处阶段并解释依据。"),
    ]
    stages = []
    for index, (title, intro) in enumerate(titles[: max(3, min(4, len(point_chunks) + 1))]):
        points = point_chunks[index] if index < len(point_chunks) else lifecycle_points[-2:] or lifecycle_points[:2]
        point_text = "、".join(points or lifecycle_points[:3])
        tasks = [
            f"围绕 {point_text} 阅读教材片段，梳理本阶段最关键的概念、任务和产物。",
            f"结合阶段顺序说明 {point_text} 与前后环节如何衔接，避免边界混淆。",
            f"把 {point_text} 写成简短清单、流程图或判断依据，形成自己的阶段框架。",
        ]
        practice = [
            f"完成与 {point_text} 相关的概念辨析、顺序判断或输入输出匹配题。",
            "如果能结合案例说明“这一阶段为什么不能跳过”，说明理解已经比较到位。",
        ]
        metrics = [
            f"能准确解释 {point_text} 的核心任务、代表性产物和与相邻阶段的关系。",
            "能根据错题定位自己究竟是概念没懂、顺序混淆，还是案例判断不稳。",
        ]
        stages.append(_render_stage(index, title, f"{intro} 当前学习目标聚焦：{goal}。", points=points, tasks=tasks, practice=practice, metrics=metrics))
    return stages


def _build_dynamic_general_stages(goal: str, points: list[str]) -> list[str]:
    ordered = _unique_points(points) or ["软件生命周期", "需求分析", "软件测试"]
    chunks = _chunk_points(ordered, 2)
    stage_templates = [
        ("核心概念澄清", "先把当前主题中最容易混淆的概念、定义和作用说清楚。"),
        ("关联关系梳理", "把相邻知识点之间的顺序、边界、输入输出和阶段产物串起来。"),
        ("案例分析应用", "放到课程案例或项目情境中，判断它们实际怎么使用。"),
        ("薄弱点回补强化", "针对错题和薄弱点做一次定向补强，避免只会背概念。"),
    ]
    stage_count = 2 if len(ordered) <= 2 else 3 if len(ordered) <= 4 else 4
    stages = []
    for index in range(stage_count):
        base_title, intro = stage_templates[index]
        current_points = chunks[index] if index < len(chunks) else ordered[-2:]
        point_text = "、".join(current_points)
        tasks = [
            f"围绕 {point_text} 阅读课程知识库，提炼关键词、核心结论和常见误区。",
            f"说明 {point_text} 分别解决什么问题，以及它们在软件工程流程中的位置。",
        ]
        if index >= 1:
            tasks.append(f"把 {point_text} 与前面阶段内容对照起来，找出容易混淆的边界。")
        if index >= 2:
            tasks.append(f"结合小案例判断 {point_text} 在真实项目中应该怎样落地。")
        practice = [
            f"完成与 {point_text} 相关的判断题、简答题或匹配题。",
            "根据练习结果记录自己最容易混淆的概念和判断依据。",
        ]
        metrics = [
            f"能用自己的话解释 {point_text} 的定义、作用和与其他知识点的关系。",
            "能指出至少 1 个常见误区，并说明为什么错。",
        ]
        stages.append(_render_stage(index, f"{point_text}{base_title}", f"{intro} 当前学习目标聚焦：{goal}。", points=current_points, tasks=tasks, practice=practice, metrics=metrics))
    return stages


def _build_fast_path_content(profile: dict, payload: dict | None = None) -> str:
    points = _profile_points(profile, payload)
    goal = str((payload or {}).get("learning_need") or profile.get("study_goal") or "掌握软件工程核心知识").strip()
    all_text = " ".join(
        str(item or "")
        for item in [
            goal,
            profile.get("error_prone_points"),
            profile.get("weak_points"),
            profile.get("current_topic"),
            (payload or {}).get("adjustment"),
        ]
    )
    lifecycle_hits = [item for item in LIFECYCLE_STAGE_POINTS if item in all_text]
    is_lifecycle_plan = "软件生命周期" in all_text or len(lifecycle_hits) >= 3 or "先后顺序" in all_text or "阶段产物" in all_text
    if is_lifecycle_plan:
        lifecycle_points = ["软件生命周期", *[item for item in LIFECYCLE_STAGE_POINTS if item in all_text]]
        if len(lifecycle_points) < 5:
            lifecycle_points = ["软件生命周期", *LIFECYCLE_STAGE_POINTS]
        lifecycle_points = list(dict.fromkeys(lifecycle_points))
        stages = _build_dynamic_lifecycle_stages(goal, lifecycle_points)
        return normalize_markdown(
            "\n\n".join(
                [
                    "# 个性化学习路径",
                    *stages,
                    "## 动态调整建议\n如果基础概念理解不稳，优先回到前两个阶段补概念和阶段边界；如果案例判断或产物辨析不稳，优先强化后半段的案例与迁移练习。",
                    f"## 参考依据\n本路径依据当前学生画像、学习目标、薄弱知识点和本地软件工程课程知识库生成。覆盖知识点包括：{'、'.join(lifecycle_points[:8])}。",
                ]
            )
        )
    stages = _build_dynamic_general_stages(goal, points)
    return normalize_markdown(
        "\n\n".join(
            [
                "# 个性化学习路径",
                *stages,
                "## 动态调整建议\n如果概念题错误较多，优先回到前置阶段补定义和边界；如果案例题错误较多，优先强化后置阶段的迁移应用。",
                f"## 参考依据\n本路径依据当前学生画像、学习目标、薄弱知识点和本地软件工程课程知识库生成。重点覆盖：{'、'.join((points or ['课程核心知识'])[:8])}。",
            ]
        )
    )


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
    title_hits = [item for item in KNOWN_POINTS if item in str(title or "")]
    hits = title_hits or [item for item in KNOWN_POINTS if item in block]
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


def _safe_json_text(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _adaptive_stage_summary(user_id: int, session_id: int, stages: list[dict], profile: dict | None = None) -> dict:
    profile = profile or {}
    mastery_rows = mysql_db.query_all(
        "SELECT knowledge_point, mastery_score, weak_reason FROM mastery_record WHERE user_id=%s AND profile_session_id=%s ORDER BY update_time DESC",
        (user_id, session_id),
    )
    if not mastery_rows:
        mastery_rows = mysql_db.query_all(
            "SELECT knowledge_point, mastery_score, weak_reason FROM mastery_record WHERE user_id=%s ORDER BY update_time DESC",
            (user_id,),
        )
    event_rows = mysql_db.query_all(
        "SELECT event_type, knowledge_point, detail, create_time FROM learning_event WHERE user_id=%s AND profile_session_id=%s ORDER BY id DESC LIMIT 200",
        (user_id, session_id),
    )
    try:
        feedback_rows = mysql_db.query_all(
            """
            SELECT rf.rating, rf.comment, rf.create_time, sr.resource_type, sr.title, sr.metadata
            FROM resource_feedback rf
            LEFT JOIN study_resource sr ON sr.id = rf.resource_id
            WHERE rf.user_id=%s AND (rf.profile_session_id=%s OR rf.profile_session_id IS NULL)
            ORDER BY rf.id DESC
            LIMIT 120
            """,
            (user_id, session_id),
        )
    except Exception:
        # Older deployments do not yet have resource_feedback.profile_session_id.
        feedback_rows = mysql_db.query_all(
            """
            SELECT rf.rating, rf.comment, rf.create_time, sr.resource_type, sr.title, sr.metadata
            FROM resource_feedback rf
            LEFT JOIN study_resource sr ON sr.id = rf.resource_id
            WHERE rf.user_id=%s
            ORDER BY rf.id DESC
            LIMIT 120
            """,
            (user_id,),
        )
    weak_text = " ".join(
        str(item or "")
        for item in [
            profile.get("weak_points"),
            profile.get("weak_knowledge_points"),
            " ".join(str(row.get("knowledge_point") or "") for row in mastery_rows if int(row.get("mastery_score") or 0) < 70),
        ]
    )
    completed_stage_indexes = set()
    stage_items = []
    for stage in stages:
        points = [str(item or "").strip() for item in (stage.get("points") or []) if str(item or "").strip()]
        stage_text = " ".join([stage.get("title") or "", stage.get("goal") or "", " ".join(points)])
        weak_hits = sum(1 for point in points if point and point in weak_text)
        quiz_hits = 0
        resource_usage_hits = 0
        completion_hits = 0
        low_rating_hits = 0
        high_rating_hits = 0
        notes = []
        for event in event_rows:
            detail = _safe_json_text(event.get("detail"), {})
            event_text = " ".join(
                str(item or "")
                for item in [
                    event.get("knowledge_point"),
                    detail.get("title") if isinstance(detail, dict) else "",
                    detail.get("resource_type") if isinstance(detail, dict) else "",
                ]
            )
            if isinstance(detail, dict) and detail.get("stage_index") == stage.get("index"):
                if event.get("event_type") == "complete_stage":
                    completed_stage_indexes.add(stage.get("index"))
                    completion_hits += 1
                elif event.get("event_type") in {"finish_quiz", "retry_wrong_book"}:
                    quiz_hits += 1
                elif event.get("event_type") in {"resource_usage", "resource_feedback"}:
                    resource_usage_hits += 1
            elif any(point and point in event_text for point in points):
                if event.get("event_type") in {"finish_quiz", "retry_wrong_book"}:
                    quiz_hits += 1
                elif event.get("event_type") in {"resource_usage", "resource_feedback"}:
                    resource_usage_hits += 1
        for row in feedback_rows:
            metadata = _safe_json_text(row.get("metadata"), {})
            title_text = " ".join(str(item or "") for item in [row.get("title"), row.get("resource_type"), row.get("comment")])
            if (isinstance(metadata, dict) and metadata.get("stage_index") == stage.get("index")) or any(point and point in title_text for point in points):
                rating = int(row.get("rating") or 0)
                if rating >= 4:
                    high_rating_hits += 1
                elif rating and rating <= 2:
                    low_rating_hits += 1
        priority = weak_hits * 3 + quiz_hits * 2 + low_rating_hits * 2 + resource_usage_hits - high_rating_hits - completion_hits * 2
        if weak_hits:
            notes.append("存在当前薄弱知识点，需要优先补强。")
        if low_rating_hits:
            notes.append("已有资源反馈偏弱，建议调整讲解方式或难度。")
        if quiz_hits:
            notes.append("近期练习记录较多，可结合错题结果继续巩固。")
        if high_rating_hits:
            notes.append("已有资源反馈较好，可继续保持当前资源风格。")
        if completion_hits:
            notes.append("该阶段已有完成记录，可降低优先级。")
        stage_items.append(
            {
                "index": stage.get("index"),
                "title": stage.get("title"),
                "priority_score": max(priority, 0),
                "completed": stage.get("index") in completed_stage_indexes,
                "weak_hits": weak_hits,
                "quiz_hits": quiz_hits,
                "resource_usage_hits": resource_usage_hits,
                "low_rating_hits": low_rating_hits,
                "high_rating_hits": high_rating_hits,
                "notes": notes[:3],
            }
        )
    ranked = sorted(stage_items, key=lambda item: (-item["priority_score"], item["completed"], item["index"] or 99))
    focus = [item for item in ranked if item["priority_score"] > 0][:3]
    next_tasks = [
        f"优先回到第{item['index']}阶段“{item['title']}”，{item['notes'][0] if item['notes'] else '继续结合反馈完成补强。'}"
        for item in focus
    ]
    if not next_tasks and ranked:
        next_tasks = [f"按既定顺序继续推进第{ranked[0]['index']}阶段“{ranked[0]['title']}”，并结合练习结果滚动调整。"]
    summary = "；".join(next_tasks[:2])
    preferred_resource = str(profile.get("preferred_resource") or "").strip()
    weak_points = str(profile.get("weak_knowledge_points") or profile.get("weak_points") or "").strip()
    explanation_parts = []
    if preferred_resource and preferred_resource not in {"", "待进一步观察"}:
        explanation_parts.append(f"你最近对{preferred_resource}类资源反馈更稳定")
    if weak_points and weak_points not in {"", "待进一步观察"}:
        explanation_parts.append(f"当前薄弱点仍集中在“{weak_points[:40]}”")
    if focus:
        top = focus[0]
        explanation_parts.append(f"因此系统优先强化第{top['index']}阶段“{top['title']}”")
        if top.get("quiz_hits"):
            explanation_parts.append("并结合近期练习结果继续补强")
        elif top.get("low_rating_hits"):
            explanation_parts.append("并调整后续资源的讲解方式与难度")
        else:
            explanation_parts.append("并继续推送更匹配当前状态的阶段资源")
    adaptive_explanation = "，".join(explanation_parts) + "。" if explanation_parts else "系统正在根据练习结果、资源反馈和阶段完成情况，持续优化后续学习顺序与资源推送。"
    return {
        "focus_stage_indexes": [item["index"] for item in focus],
        "focus_summary": summary or "当前学习反馈较稳定，可按既定顺序继续推进。",
        "adaptive_explanation": adaptive_explanation,
        "stage_rankings": ranked,
        "next_tasks": next_tasks[:4],
    }


def _profile_basis(profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "knowledge_base": profile.get("knowledge_base") or profile.get("knowledge_level") or "待进一步观察",
        "weak_points": profile.get("error_prone_points") or profile.get("weak_points") or "待进一步观察",
        "study_goal": profile.get("study_goal") or "待进一步观察",
        "summary": profile.get("profile_summary") or "本路径基于你的知识基础、薄弱点和学习目标生成。",
    }


def _normalize_stage_progress_rows(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows or []:
        detail = _safe_json(row.get("detail"), {})
        result.append(
            {
                "id": row.get("id"),
                "stage_index": int(detail.get("stage_index") or 0),
                "stage_title": str(detail.get("stage_title") or ""),
                "completed": bool(detail.get("completed", True)),
                "knowledge_points": detail.get("knowledge_points") or [],
                "time": str(row.get("create_time") or ""),
            }
        )
    return result


def _path_query(profile: dict, payload: dict | None = None) -> str:
    payload = payload or {}
    values = [
        payload.get("learning_need"),
        payload.get("adjustment"),
        profile.get("weak_points"),
        profile.get("error_prone_points"),
        profile.get("current_topic"),
        profile.get("study_goal"),
        profile.get("selected_primary_knowledge_title"),
        profile.get("course_progress"),
        "软件工程",
    ]
    parts = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in parts:
            parts.append(text)
    return " ".join(parts)


def _retrieve_path_sources(query: str, profile: dict, top_k: int = 3) -> list[dict]:
    sources = retrieve_knowledge_items(query, top_k=top_k)
    if sources:
        return sources
    return select_profile_knowledge_items(query, profile=profile, top_k=top_k)


def _build_planner_prompt(profile_text: str, knowledge: str, learning_need: str) -> str:
    return f"""
你是软件工程课程学习规划师。请基于学生画像、学生本次学习需求和教材原文生成个性化学习路径。

输出要求：
1. 只输出普通 Markdown 正文，不要代码围栏，不要 JSON，不要 ASCII 图，不要复杂表格，不要 emoji。
2. 标题层级必须统一：一级标题用“# 个性化学习路径”，二级标题用“## 阶段一：...”这类形式，三级标题用“### 学习安排”。
3. 根据主题复杂度动态生成 2 到 5 个学习阶段，不能只生成 1 个阶段；阶段之间应体现递进关系，但不要机械重复“基础理解 → 关系建构 → 练习应用”。
4. 阶段标题必须围绕学生真实薄弱点、课程章节边界和任务难度规划，避免空泛标题，也不要简单把抽取到的前三个知识点直接拼接成标题。
5. 如果学生学习的是软件生命周期、开发流程、阶段顺序或阶段产物，应优先按“总览认知 → 阶段边界 → 衔接与产物 → 案例应用”这类逻辑组织，但阶段数仍应按实际内容决定。
6. 每个阶段固定包含五项，且五项名称必须一致：目标、学习任务、推荐资源、练习方式、评估指标。
7. 每个阶段写成短段落和项目符号，不要把所有内容挤在一行。
8. 内容要清楚说明学习顺序、为什么这样学、需要用到哪些文档/题库/视频/案例。
9. 最后添加“## 动态调整建议”和“## 参考依据”两个小节。
10. 只能依据教材原文和学生画像，不要编造不存在的页码、图片和结论。

请严格按这个模板组织，阶段数量可以动态变化：

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

## 阶段二：关系梳理与流程建构
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

## 阶段四：薄弱点回补强化
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

学生本次学习需求：
{learning_need or '未单独提供，请结合学生画像判断'}

学生画像：
{profile_text}

教材原文：
{knowledge or '当前未检索到充分教材原文，请严格根据学生画像和课程常识生成保守学习路径，不要编造页码。'}
""".strip()


def _valid_llm_path(path_content: str) -> tuple[bool, str]:
    content = normalize_markdown(path_content)
    if not content or _is_model_error_text(content):
        return False, "模型返回为空或调用失败"
    stages = _parse_path_stages(content)
    if not 2 <= len(stages) <= 5:
        return False, f"阶段数量不在2到5之间：{len(stages)}"
    required_labels = ["目标", "学习任务", "推荐资源", "练习方式", "评估指标"]
    missing = [label for label in required_labels if f"**{label}" not in content]
    if missing:
        return False, f"缺少固定栏目：{'、'.join(missing)}"
    titles = [stage.get("title", "") for stage in stages]
    if len(set(titles)) != len(titles):
        return False, "阶段标题重复"
    return True, "ok"


def _hybrid_path_content(profile: dict, payload: dict, query: str) -> tuple[str, list[dict], dict]:
    sources = _retrieve_path_sources(query, profile, top_k=3)
    knowledge = format_knowledge_items(sources)
    profile_text = json.dumps(profile, ensure_ascii=False, default=str)
    learning_need = str(payload.get("learning_need") or payload.get("adjustment") or profile.get("study_goal") or "")
    prompt = _build_planner_prompt(profile_text, knowledge, learning_need)
    fallback_content = _build_fast_path_content(profile, payload)
    meta = {"strategy": "hybrid_llm_first", "fallback_used": False, "validation": ""}
    try:
        llm_content = normalize_markdown(spark_chat(prompt))
        valid, reason = _valid_llm_path(llm_content)
        meta["validation"] = reason
        if valid:
            return llm_content, sources, meta
    except Exception as exc:
        meta["validation"] = f"模型规划异常：{exc}"
    meta["fallback_used"] = True
    return fallback_content, sources, meta


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

        query = _path_query(profile, payload)
        path_meta = {"strategy": "legacy_full_generation" if payload.get("full_generation") else "hybrid_llm_first", "fallback_used": False, "validation": ""}
        if not payload.get("full_generation"):
            path_content, sources, path_meta = _hybrid_path_content(profile, payload, query)
        else:
            sources = retrieve_knowledge_items(query, top_k=3)
            knowledge = retrieve_knowledge(query, top_k=3)
            prompt = f"""
    你是软件工程课程学习规划师。请基于学生画像和教材原文生成个性化学习路径。

    输出要求：
    1. 只输出普通 Markdown 正文，不要代码围栏，不要 JSON，不要 ASCII 图，不要复杂表格，不要 emoji。
    2. 标题层级必须统一：一级标题用“# 个性化学习路径”，二级标题用“## 阶段一：...”这类形式，三级标题用“### 学习安排”。
    3. 根据主题复杂度动态生成 2 到 5 个学习阶段，不能只生成 1 个阶段；阶段之间应体现递进关系，但不要机械重复同一套标题。
    4. 每个阶段固定包含五项，且五项名称必须一致：目标、学习任务、推荐资源、练习方式、评估指标。
    5. 每个阶段写成短段落和项目符号，不要把所有内容挤在一行。
    6. 内容要清楚说明学习顺序、为什么这样学、需要用到哪些文档/题库/视频/案例。
    7. 最后添加“## 动态调整建议”和“## 参考依据”两个小节。
    8. 只能依据教材原文和学生画像，不要编造不存在的页码、图片和结论。

    请严格按这个模板组织，阶段数量可以动态变化：

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

    ## 阶段四：薄弱点回补强化
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

        safety = safety_agent.review(path_content, sources) if payload.get("full_generation") else {"passed": True, "risk": "混合路径生成：大模型优先规划，格式校验失败时模板兜底", "sources": sources, "path_meta": path_meta}
        logger.warning(
            "[PathPlanner] session=%s strategy=%s fallback_used=%s validation=%s source_count=%s stage_count=%s",
            session_id,
            path_meta.get("strategy"),
            path_meta.get("fallback_used"),
            path_meta.get("validation"),
            len(sources or []),
            len(_parse_path_stages(path_content)),
        )
        path_id = mysql_db.insert("study_path", {"user_id": user_id, "profile_session_id": session_id, "path_content": path_content, "status": "active"})
        return success({"id": path_id, "user_id": user_id, "profile_session_id": session_id, "path_content": path_content, "status": "active", "sources": sources, "safety": safety, "path_meta": path_meta}, "学习路径生成成功")
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
        try:
            adaptive = _adaptive_stage_summary(request.user_id, session_id, stages, profile)
        except Exception:
            logger.exception("Adaptive stage summary failed; returning the learning path without adaptive ranking")
            adaptive = {
                "focus_stage_indexes": [],
                "focus_summary": "",
                "adaptive_explanation": "学习路径与资源已正常加载，动态反馈分析将在数据兼容后继续更新。",
                "next_tasks": [],
                "stage_rankings": [],
            }
        adaptive_focus_indexes = set(adaptive.get("focus_stage_indexes") or [])
        stages = [
            {
                **stage,
                "adaptive_focus": stage.get("index") in adaptive_focus_indexes,
                "adaptive_priority": next((item.get("priority_score") for item in adaptive.get("stage_rankings", []) if item.get("index") == stage.get("index")), 0),
                "adaptive_notes": next((item.get("notes") for item in adaptive.get("stage_rankings", []) if item.get("index") == stage.get("index")), []),
            }
            for stage in stages
        ]
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
            "adaptive_focus": adaptive.get("focus_summary"),
            "adaptive_explanation": adaptive.get("adaptive_explanation"),
            "next_tasks": adaptive.get("next_tasks", []),
            "stage_rankings": adaptive.get("stage_rankings", []),
            "stages": stages,
            "resources": resources,
            "path_content": path.get("path_content") if path else "",
        }
        return success(data, "一体化学习路径查询成功")
    except Exception as exc:
        logger.exception("Integrated learning path query failed")
        return fail("一体化学习路径查询失败", 500, {"error": str(exc)})



@path_bp.get("/stage-progress")
@login_required
def get_stage_progress():
    try:
        session = resolve_profile_session(request.user_id, request.args.to_dict(), create_if_missing=False)
        if not session:
            return success({"profile_session_id": None, "items": []}, "暂无画像会话阶段进度")
        rows = mysql_db.query_all(
            """
            SELECT id, detail, create_time
            FROM learning_event
            WHERE user_id=%s AND profile_session_id=%s AND event_type='complete_stage'
            ORDER BY create_time DESC, id DESC
            """,
            (request.user_id, session["id"]),
        )
        latest_by_stage = {}
        for item in _normalize_stage_progress_rows(rows):
            stage_index = item.get("stage_index")
            if stage_index and stage_index not in latest_by_stage:
                latest_by_stage[stage_index] = item
        return success(
            {
                "profile_session_id": session["id"],
                "items": sorted(latest_by_stage.values(), key=lambda item: item["stage_index"]),
            },
            "阶段进度查询成功",
        )
    except Exception as exc:
        return fail("阶段进度查询失败", 500, {"error": str(exc)})


@path_bp.post("/stage-progress")
@login_required
def save_stage_progress():
    try:
        payload = request.get_json(silent=True) or {}
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        if not session:
            return fail("未找到画像会话，无法记录阶段进度", 404)

        stage_index = int(payload.get("stage_index") or 0)
        if stage_index <= 0:
            return fail("stage_index 无效", 400)

        detail = {
            "stage_index": stage_index,
            "stage_title": str(payload.get("stage_title") or "")[:120],
            "completed": bool(payload.get("completed", True)),
            "knowledge_points": payload.get("knowledge_points") if isinstance(payload.get("knowledge_points"), list) else [],
            "path_id": payload.get("path_id"),
        }
        knowledge_point = "、".join(str(item) for item in detail["knowledge_points"][:3] if str(item).strip()) or detail["stage_title"] or f"第{stage_index}阶段"

        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "profile_session_id": session["id"],
                "event_type": "complete_stage",
                "knowledge_point": knowledge_point,
                "detail": json.dumps(detail, ensure_ascii=False),
            },
        )

        jar_added = []
        if detail["completed"] and detail["knowledge_points"]:
            from api.knowledge_jar_api import record_knowledge_collections

            jar_added = record_knowledge_collections(
                request.user_id,
                session["id"],
                detail["knowledge_points"],
                source="stage_complete",
                source_label="完成学习阶段自动沉淀",
                stage_index=stage_index,
                stage_title=detail["stage_title"],
                auto_collected=True,
            )

        from api.profile_api import _aggregate_profile_payload, _persist_portrait_snapshot, _refresh_aggregate_profile

        aggregate_profile = _aggregate_profile_payload(
            request.user_id,
            _refresh_aggregate_profile(request.user_id),
            refresh_scoring=True,
        )
        _persist_portrait_snapshot(
            user_id=request.user_id,
            profile_session_id=session["id"],
            profile=aggregate_profile,
            portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
            trigger_source="path_stage_complete",
            force=True,
        )

        return success(
            {
                "profile_session_id": session["id"],
                "stage_index": stage_index,
                "completed": detail["completed"],
                "knowledge_jar_added": jar_added,
                "aggregate_profile": aggregate_profile,
            },
            "阶段进度已记录，画像已刷新",
        )
    except Exception as exc:
        return fail("阶段进度记录失败", 500, {"error": str(exc)})


@path_bp.post("/feedback")
@login_required
def submit_path_feedback():
    try:
        payload = request.get_json(silent=True) or {}
        session = resolve_profile_session(request.user_id, payload, create_if_missing=False)
        if not session:
            return fail("未找到画像会话，无法记录学习反馈", 404)

        stage_index = int(payload.get("stage_index") or 0)
        stage_title = str(payload.get("stage_title") or "")[:120]
        feedback_type = str(payload.get("feedback_type") or "general_feedback")[:40]
        feedback_text = str(payload.get("feedback_text") or "").strip()[:300]
        knowledge_points = payload.get("knowledge_points") if isinstance(payload.get("knowledge_points"), list) else []

        detail = {
            "stage_index": stage_index,
            "stage_title": stage_title,
            "feedback_type": feedback_type,
            "feedback_text": feedback_text,
            "knowledge_points": knowledge_points,
        }
        knowledge_point = "、".join(str(item) for item in knowledge_points[:3] if str(item).strip()) or stage_title or f"第{stage_index or 0}阶段"

        mysql_db.insert(
            "learning_event",
            {
                "user_id": request.user_id,
                "profile_session_id": session["id"],
                "event_type": feedback_type,
                "knowledge_point": knowledge_point,
                "detail": json.dumps(detail, ensure_ascii=False),
            },
        )

        from api.profile_api import _aggregate_profile_payload, _persist_portrait_snapshot, _refresh_aggregate_profile

        aggregate_profile = _aggregate_profile_payload(
            request.user_id,
            _refresh_aggregate_profile(request.user_id),
            refresh_scoring=True,
        )
        _persist_portrait_snapshot(
            user_id=request.user_id,
            profile_session_id=session["id"],
            profile=aggregate_profile,
            portrait_scoring=aggregate_profile.get("portrait_scoring") or {},
            trigger_source="path_feedback",
            force=True,
        )

        return success(
            {
                "profile_session_id": session["id"],
                "feedback_type": feedback_type,
                "aggregate_profile": aggregate_profile,
            },
            "学习反馈已记录，画像已刷新",
        )
    except Exception as exc:
        return fail("学习反馈记录失败", 500, {"error": str(exc)})

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



