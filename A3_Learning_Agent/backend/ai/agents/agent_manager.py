import json
import logging
import time
import uuid
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, Optional, List

from ai.llm_api import audit_content
from ai.rag import build_resource_context, retrieve_knowledge_items, select_profile_knowledge_items
from .code_agent import CodeAgent
from .document_agent import DocumentAgent
from .mindmap_agent import MindMapAgent
from .planner_agent import PlannerAgent
from .profile_agent import ProfileAgent
from .quality_agent import QualityAgent
from .quiz_agent import QuizAgent
from .reading_agent import ReadingAgent
from .safety_agent import SafetyAgent
from .video_agent import VideoAgent


logger = logging.getLogger(__name__)


class AgentManager:
    """Multi-agent resource generation pipeline backed by the local software-engineering KB."""

    PROFILE_FIELDS = [
        "knowledge_level",
        "study_style",
        "weak_points",
        "study_goal",
        "study_time_prefer",
        "course_progress",
    ]

    def __init__(self):
        self.profile_agent = ProfileAgent()
        self.planner_agent = PlannerAgent()
        self.resource_agents = {
            "doc": DocumentAgent(),
            "quiz": QuizAgent(),
            "reading": ReadingAgent(),
            "mindmap": MindMapAgent(),
            "code": CodeAgent(),
            "video": VideoAgent(),
        }
        self.quality_agent = QualityAgent()
        self.safety_agent = SafetyAgent()

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="milliseconds")

    def _build_context(
        self,
        dialogue_text: str,
        stored_profile: Optional[Dict[str, Any]],
        request_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        request_data = request_data or {}
        stored_profile = stored_profile or {}
        if stored_profile:
            profile = {
                field: stored_profile.get(field) or "待进一步观察"
                for field in self.PROFILE_FIELDS
            }
        else:
            profile = self.profile_agent.analyze(dialogue_text)
        return {
            "major": request_data.get("major") or stored_profile.get("major") or "软件工程/计算机相关专业",
            "course": request_data.get("course") or stored_profile.get("target_course") or "软件工程",
            **profile,
            "challenge_scene": stored_profile.get("challenge_scene") or profile.get("challenge_scene"),
            "preferred_resource": stored_profile.get("preferred_resource") or profile.get("preferred_resource"),
            "profile_summary": stored_profile.get("profile_summary") or profile.get("profile_summary"),
            "current_need": request_data.get("learning_need") or dialogue_text or profile.get("study_goal"),
            "preferred_resource_types": request_data.get("preferred_resource_types") or ["doc", "quiz", "reading", "mindmap", "code", "video"],
        }

    def _build_query(self, dialogue_text: str, context: Dict[str, Any]) -> str:
        parts = [
            context.get("weak_points"),
            context.get("study_goal"),
            context.get("course_progress"),
            context.get("current_need"),
            dialogue_text,
        ]
        return " ".join(str(part) for part in parts if part).strip() or "软件工程 学习资源"

    @staticmethod
    def _build_stage_query(stage: Dict[str, Any], context: Dict[str, Any], base_query: str = "") -> str:
        parts = [
            stage.get("stage_title"),
            stage.get("stage_goal"),
            stage.get("difficulty_label"),
            stage.get("retrieval_focus"),
            stage.get("analysis_focus"),
            " ".join(stage.get("stage_points") or []),
            " ".join(stage.get("retrieval_terms") or []),
            context.get("weak_points"),
            context.get("study_goal"),
            context.get("course_progress"),
            context.get("current_need"),
            base_query,
            "软件工程",
        ]
        seen = []
        for part in parts:
            text = str(part or "").strip()
            if text and text not in seen and text != "待进一步观察":
                seen.append(text)
        return " ".join(seen) or "软件工程 学习资源"

    @staticmethod
    def _stage_learning_profile(stage_index: int, raw_points: Optional[List[str]] = None) -> Dict[str, Any]:
        points_text = " ".join(str(item) for item in (raw_points or []))
        demand_topic = any(token in points_text for token in ["需求", "可行性", "软件生命周期", "数据流图"])
        if demand_topic:
            profiles = {
                1: {
                    "difficulty_label": "基础理解",
                    "stage_points": ["软件生命周期", "软件定义阶段", "问题定义", "可行性研究", "需求分析"],
                    "retrieval_terms": ["软件生命周期", "软件定义", "可行性研究", "需求分析定义", "系统必须做什么"],
                    "retrieval_focus": "优先检索概念定义、阶段位置、基本任务、输入输出和阶段顺序。",
                    "analysis_focus": "从零基础解释概念边界：先讲软件生命周期和软件定义阶段，再讲需求分析为什么出现。",
                },
                2: {
                    "difficulty_label": "方法建构",
                    "stage_points": ["需求获取", "需求建模", "数据流图", "数据字典", "需求规格说明"],
                    "retrieval_terms": ["需求获取", "需求建模", "数据流图", "数据字典", "规格说明书", "功能需求"],
                    "retrieval_focus": "优先检索方法步骤、建模工具、需求规格说明、功能性能约束和阶段产物。",
                    "analysis_focus": "假设已懂基本定义，重点讲方法流程、模型工具、需求文档如何形成。",
                },
                3: {
                    "difficulty_label": "迁移应用",
                    "stage_points": ["需求验证", "需求复审", "可维护性复审", "需求变更", "案例练习"],
                    "retrieval_terms": ["需求验证", "需求复审", "可维护性复审", "需求变更", "系统界面", "可移植性", "案例"],
                    "retrieval_focus": "优先检索复审、验证、可维护性、常见错误、案例迁移和质量风险。",
                    "analysis_focus": "面向提升应用，重点讲案例判断、错误纠正、复审检查和迁移应用。",
                },
            }
            return profiles.get(stage_index, profiles[3])
        generic_profiles = {
            1: {
                "difficulty_label": "基础理解",
                "stage_points": ["软件生命周期", "核心概念", "阶段任务", "输入输出"],
                "retrieval_terms": ["软件生命周期", "软件工程定义", "阶段任务", "输入 输出"],
                "retrieval_focus": "优先检索定义、位置、基本任务和输入输出。",
                "analysis_focus": "从基础概念和阶段位置讲起。",
            },
            2: {
                "difficulty_label": "方法建构",
                "stage_points": ["方法流程", "模型工具", "阶段产物", "前后衔接"],
                "retrieval_terms": ["方法", "流程", "模型", "阶段产物", "设计"],
                "retrieval_focus": "优先检索方法流程、工具、产物和阶段关系。",
                "analysis_focus": "讲清方法之间的关系和流程衔接。",
            },
            3: {
                "difficulty_label": "迁移应用",
                "stage_points": ["案例应用", "质量风险", "常见误区", "复审评估"],
                "retrieval_terms": ["案例", "风险", "复审", "测试", "维护"],
                "retrieval_focus": "优先检索案例、风险、误区、复审和实践应用。",
                "analysis_focus": "通过案例和练习完成应用提升。",
            },
        }
        return generic_profiles.get(stage_index, generic_profiles[3])

    @classmethod
    def _apply_stage_progression(cls, stage: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        stage_index = int(stage.get("stage_index") or 1)
        raw_points = stage.get("stage_points") or cls._extract_stage_points(" ".join(str(context.get(key) or "") for key in ["weak_points", "study_goal", "current_need"]))
        profile = cls._stage_learning_profile(stage_index, raw_points)
        merged_points = []
        for point in profile.get("stage_points") or []:
            if point and point not in merged_points:
                merged_points.append(point)
        for point in raw_points or []:
            if point and point not in merged_points and len(merged_points) < 6:
                merged_points.append(point)
        return {
            **stage,
            **profile,
            "stage_points": merged_points[:6],
        }

    @staticmethod
    def _extract_stage_points(text: str) -> List[str]:
        known = ["需求分析", "总体设计", "详细设计", "软件测试", "软件生命周期", "软件过程", "可行性研究", "软件维护", "编码实现", "数据流图", "用例图", "模块划分", "调试"]
        points = [item for item in known if item in str(text or "")]
        return points[:5] or [str(text or "课程核心知识")[:24] or "课程核心知识"]

    @staticmethod
    def _extract_stage_goal(block: str) -> str:
        import re
        for label in ["目标", "学习任务"]:
            match = re.search(rf"\*\*{label}[：:]?\*\*\s*([^\n]+)", block)
            if match:
                return match.group(1).strip(" #*_`>-：:")[:180]
        lines = [line.strip(" #*_`>-：:") for line in str(block or "").splitlines()[1:] if line.strip()]
        useful = [line for line in lines if not line.startswith(("推荐资源", "练习方式", "评估指标"))]
        return (useful[0] if useful else "围绕当前阶段知识点完成学习任务。")[:180]

    def _parse_stage_specs(self, path_content: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        import re
        content = str(path_content or "")
        stage_pattern = r"\n(?=##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段))"
        blocks = [item for item in re.split(stage_pattern, content) if re.match(r"^##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段)", item.strip())]
        stages = []
        for index, block in enumerate(blocks):
            first_line = block.strip().splitlines()[0] if block.strip() else ""
            title = re.sub(r"^##\s*(?:阶段[一二三四五六七八九十\d]+|第\d+阶段)[：:、.．\s]*", "", first_line).strip(" #*_`>-：:") or f"学习阶段{index + 1}"
            stage_points = self._extract_stage_points(f"{title}\n{block}")
            stage_goal = self._extract_stage_goal(block)
            stages.append(self._apply_stage_progression({"stage_index": index + 1, "stage_id": f"stage_{index + 1}", "stage_title": title, "stage_goal": stage_goal, "stage_points": stage_points}, context))
        if len(stages) >= 3:
            return stages[:4]
        points = self._extract_stage_points(" ".join(str(context.get(key) or "") for key in ["weak_points", "study_goal", "current_need"]))
        if stages:
            fallback_specs = [
                {"stage_title": "方法关系建构", "stage_goal": "建立相关方法、流程和阶段之间的关系。", "stage_points": points},
                {"stage_title": "练习与应用巩固", "stage_goal": "通过练习、案例和应用任务完成迁移。", "stage_points": points},
            ]
            existing_titles = {stage.get("stage_title") for stage in stages}
            for item in fallback_specs:
                if len(stages) >= 3:
                    break
                if item["stage_title"] in existing_titles:
                    continue
                next_index = len(stages) + 1
                stages.append(self._apply_stage_progression({"stage_index": next_index, "stage_id": f"stage_{next_index}", **item}, context))
            return stages[:3]
        return [
            self._apply_stage_progression({"stage_index": 1, "stage_id": "stage_1", "stage_title": "基础概念澄清", "stage_goal": "理解核心概念、阶段产物和输入输出关系。", "stage_points": points[:2] or points}, context),
            self._apply_stage_progression({"stage_index": 2, "stage_id": "stage_2", "stage_title": "方法关系建构", "stage_goal": "建立相关方法、流程和阶段之间的关系。", "stage_points": points}, context),
            self._apply_stage_progression({"stage_index": 3, "stage_id": "stage_3", "stage_title": "练习与应用巩固", "stage_goal": "通过练习、案例和应用任务完成迁移。", "stage_points": points}, context),
        ]

    def _stage_context(self, context: Dict[str, Any], stage: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(context)
        merged.update(stage)
        stage_index = int(stage.get("stage_index") or 1)
        if stage_index <= 1:
            progressive_focus = "Focus on basic definitions, purpose, inputs, outputs, and order. Do not expand into complex comparisons or advanced cases."
        elif stage_index == 2:
            progressive_focus = "Focus on methods, process flow, structure relationships, and stage transitions. Assume the student already knows the basic definitions."
        else:
            progressive_focus = "Focus on cases, practice, common mistakes, quality risks, and transfer tasks. Assume the student already knows the basic concepts and flow."

        merged["weak_points"] = stage.get("stage_points") or context.get("weak_points")
        merged["difficulty_label"] = stage.get("difficulty_label")
        merged["retrieval_focus"] = stage.get("retrieval_focus")
        merged["analysis_focus"] = stage.get("analysis_focus")
        merged["study_goal"] = f"{stage.get('stage_title')}: {stage.get('stage_goal')}"
        merged["current_need"] = (
            f"Generate resources only for stage {stage.get('stage_index')}: {stage.get('stage_title')}. "
            f"Stage goal: {stage.get('stage_goal')}. "
            f"Stage knowledge points: {' / '.join(stage.get('stage_points') or [])}. "
            f"{progressive_focus} "
            "Do not repeat other stages and do not merge the whole path into one generic explanation."
        )
        merged["stage_unique_instruction"] = (
            f"This resource must clearly represent stage {stage.get('stage_index')} and remain different from the other stages. "
            f"Title, examples, explanation focus, and self-check items must all center on {stage.get('stage_title')}. "
            f"{progressive_focus}"
        )
        return merged

    @staticmethod
    def _safe_evidence(items: List[dict]) -> List[dict]:
        evidence = []
        for item in items or []:
            metadata = item.get("metadata") or {}
            section_path = metadata.get("section_path") or []
            if not isinstance(section_path, list):
                section_path = [str(section_path)] if section_path else []
            evidence.append(
                {
                    "title": metadata.get("title") or "",
                    "content_preview": str(item.get("content") or "")[:220],
                    "section_path": section_path,
                    "learning_location": metadata.get("learning_location") or {},
                    "pages": metadata.get("pages") or [],
                    "source_file": metadata.get("source") or item.get("source") or "",
                }
            )
        return evidence

    @staticmethod
    def _knowledge_text_for_model(items: List[dict], primary_title: str = "") -> str:
        if not items:
            return "未检索到对应知识库片段。"

        def normalize_title(value: str) -> str:
            return re.sub(r"[^\u4e00-\u9fa5a-z0-9]+", "", str(value or "").strip().lower())

        def clean_content(value: str) -> str:
            text = str(value or "")
            text = text.replace("\n", " ")
            text = re.sub(r"(标题|章节路径|页码|内容|教材依据|教材片段重点说明|结合课程知识库内容可知)\s*[：:]\s*", "", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip(" ，。；;:：")

        cleaned = []
        for item in items:
            metadata = item.get("metadata") or {}
            title = str(metadata.get("title") or "课程核心知识").strip()
            content = clean_content(item.get("content") or "")
            if not content:
                continue
            cleaned.append({"title": title, "content": content})

        if not cleaned:
            return "未检索到对应知识库片段。"

        primary_key = normalize_title(primary_title)
        if primary_key:
            cleaned.sort(key=lambda entry: 0 if normalize_title(entry["title"]) == primary_key else 1)

        main_item = cleaned[0]
        support_items = []
        main_key = normalize_title(main_item["title"])
        for entry in cleaned[1:]:
            entry_key = normalize_title(entry["title"])
            if entry_key == main_key:
                continue
            support_items.append(entry)
            if len(support_items) >= 2:
                break

        blocks = [f"主知识点：{main_item['title']}\n教材内容：{main_item['content'][:1200]}"]
        for entry in support_items:
            blocks.append(f"补充知识点：{entry['title']}\n教材内容：{entry['content'][:700]}")
        return "\n\n".join(blocks)
    @staticmethod
    def _fast_quality(resource: Dict[str, Any], sources: List[dict]) -> Dict[str, Any]:
        content = str(resource.get("content") or "")
        resource_type = resource.get("resource_type")
        min_length = {"doc": 220, "mindmap": 80, "reading": 180}.get(resource_type, 120)
        problems = []
        if len(content) < min_length:
            problems.append(f"内容偏短，建议不少于{min_length}字符")
        if not sources:
            problems.append("缺少课程知识库来源")
        if resource_type == "mindmap" and not content.lstrip().startswith("#"):
            problems.append("思维导图不是合法的Markdown大纲")
        completeness = min(100, 55 + int(len(content) / max(min_length, 1) * 45)) if content else 0
        source_support = 90 if sources else 35
        format_ok = not problems or all("内容偏短" not in item for item in problems)
        accuracy = 90 if sources and format_ok else 60
        personalization = 85 if resource.get("personalization") else 65
        total = round(accuracy * 0.35 + personalization * 0.25 + completeness * 0.25 + source_support * 0.15)
        return {
            "accuracy": accuracy,
            "personalization": personalization,
            "completeness": completeness,
            "source_support": source_support,
            "total": total,
            "passed": total >= 75 and bool(sources) and format_ok,
            "problems": problems,
            "checks": {"fast_local_quality": True},
        }

    def _fast_generate_resource(
        self,
        resource_type: str,
        stage_context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        agent = self.resource_agents[resource_type]
        if resource_type == "doc" and hasattr(agent, "_fallback_doc_resource"):
            return agent._fallback_doc_resource(stage_context, knowledge_text)
        resource = agent._fallback_resource(stage_context, knowledge_text)
        if resource_type == "mindmap":
            points = stage_context.get("stage_points") or stage_context.get("selected_knowledge_points") or []
            primary = stage_context.get("selected_primary_knowledge_title") or (points[0] if points else stage_context.get("stage_title") or "课程核心知识")
            focus = stage_context.get("analysis_focus") or "围绕当前阶段理解知识点。"
            lines = [
                f"# {stage_context.get('stage_title') or primary}",
                "## 阶段定位",
                f"### 难度层级：{stage_context.get('difficulty_label') or '阶段学习'}",
                f"#### {focus}",
                "## 核心知识点",
            ]
            for point in points[:6]:
                lines.extend([
                    f"### {point}",
                    "#### 含义：理解它在软件工程流程中的位置和作用",
                    "#### 重点：掌握它解决的问题、依赖的信息和形成的产物",
                    "#### 应用：结合课程案例判断它如何影响后续阶段",
                    "#### 易错：不要把相邻阶段或相近概念混为一谈",
                ])
            lines.extend([
                "## 学习推进",
                "### 先看教材依据",
                "#### 把概念放回对应章节和阶段",
                "### 再做关系梳理",
                "#### 连接输入、过程、输出和后续影响",
                "### 最后完成自测",
                "#### 用例题或案例验证是否能迁移应用",
            ])
            resource["title"] = f"{stage_context.get('stage_title')}阶段知识导图"
            resource["content"] = "\n".join(lines)
            resource["knowledge_points"] = points[:6]
            resource["format"] = "markdown"
        elif resource_type == "reading":
            points = stage_context.get("stage_points") or stage_context.get("selected_knowledge_points") or []
            primary = stage_context.get("selected_primary_knowledge_title") or (points[0] if points else "课程核心知识")
            resource["title"] = f"{stage_context.get('stage_title')}拓展阅读"
            resource["content"] = "\n".join([
                f"# {stage_context.get('stage_title')}拓展阅读",
                "",
                f"本阅读围绕“{primary}”展开，难度定位为：{stage_context.get('difficulty_label') or '阶段提升'}。",
                "",
                "## 阅读目标",
                stage_context.get("analysis_focus") or "把教材知识迁移到课程案例中理解。",
                "",
                "## 教材依据摘录",
                knowledge_text[:1200],
                "",
                "## 阅读后思考",
                "- 这个知识点解决什么问题？",
                "- 它依赖哪些输入，又会产生什么输出？",
                "- 在项目案例中如果忽略它，会造成什么风险？",
            ])
            resource["knowledge_points"] = points[:6]
            resource["format"] = "markdown"
        return resource

    @staticmethod
    def _empty_resource(resource_type: str, stage: Dict[str, Any], stage_sources: List[dict]) -> Dict[str, Any]:
        message = "未检索到对应知识库片段。"
        evidence = AgentManager._safe_evidence(stage_sources)
        title = {
            "doc": f"{stage.get('stage_title')}・综合讲解文档",
            "mindmap": f"{stage.get('stage_title')}・阶段知识导图",
            "quiz": f"{stage.get('stage_title')}・基础练习题",
            "reading": f"{stage.get('stage_title')}・拓展阅读",
            "code": f"{stage.get('stage_title')}・代码案例",
            "video": f"{stage.get('stage_title')}・视频讲解",
        }.get(resource_type, f"{stage.get('stage_title')}・学习资源")
        return {
            "resource_type": resource_type,
            "title": title,
            "content": message,
            "knowledge_points": stage.get("stage_points") or [],
            "personalization": "当前阶段未检索到足够课程知识片段，因此未生成正式内容。",
            "format": "markdown",
            "agent_name": "RetrieveAgent",
            "metadata": {"evidence": evidence, "learning_location": evidence[0].get("learning_location") if evidence else {}},
        }

    def run_pipeline(
        self,
        dialogue_text: str = "",
        stored_profile: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        event_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        trace_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        result: Dict[str, Any] = {
            "trace_id": trace_id,
            "context": {},
            "profile": {},
            "plan": {},
            "knowledge": "",
            "knowledge_context": {},
            "sources": [],
            "resources": {},
            "resource_list": [],
            "trace": [],
            "errors": [],
            "safety": {},
        }

        def emit(event: Dict[str, Any]) -> None:
            if event_callback:
                event_callback({"trace_id": trace_id, "time": self._now(), **event})

        def trace(agent: str, status: str, message: str, duration_ms: int = 0, retry_count: int = 0) -> None:
            event = {
                "agent": agent,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "retry_count": retry_count,
                "time": self._now(),
            }
            result["trace"].append(event)
            emit({"type": "agent", **event})

        emit({"type": "start", "status": "running", "message": "多智能体资源生成流程已启动"})

        if dialogue_text and not audit_content(dialogue_text):
            result["errors"].append("学生输入未通过内容审核")
            trace("SafetyAgent", "failed", "学生输入未通过内容审核")
            return result

        emit({"type": "agent", "agent": "ProfileAgent", "status": "running", "message": "正在读取结构化画像并合并本次学习需求"})
        start = time.perf_counter()
        context = self._build_context(dialogue_text, stored_profile, request_data)
        result["context"] = context
        result["profile"] = {field: context.get(field) for field in self.PROFILE_FIELDS}
        trace("ProfileAgent", "completed", "已读取结构化画像并合并本次学习需求", int((time.perf_counter() - start) * 1000))

        emit({"type": "agent", "agent": "RetrieveAgent", "status": "running", "message": "正在从软件工程知识库召回可信依据"})
        start = time.perf_counter()
        query = self._build_query(dialogue_text, context)
        knowledge_context = build_resource_context(query, top_k=4, profile=context)
        sources = select_profile_knowledge_items(query, profile=context, top_k=2)
        result["knowledge_context"] = knowledge_context
        result["sources"] = sources
        result["knowledge"] = self._knowledge_text_for_model(sources)
        trace("RetrieveAgent", "completed" if sources else "warning", f"召回 {len(sources)} 个本地知识库片段", int((time.perf_counter() - start) * 1000))

        stage_specs = self._parse_stage_specs((request_data or {}).get("path_content") or "", context)
        default_resource_types = ["doc", "mindmap"]
        full_resource_types = list(self.resource_agents.keys())
        use_full_generation = bool((request_data or {}).get("full_generation"))
        allow_quality_retry = use_full_generation

        emit({"type": "agent", "agent": "PlannerAgent", "status": "running", "message": "正在规划资源主题、难度和目标"})
        start = time.perf_counter()
        if use_full_generation:
            plan = self.planner_agent.plan(context, sources)
        else:
            plan = {
                "resource_tasks": [
                    {"resource_type": item, "goal": "根据当前阶段难度和知识库片段快速生成学习资源"}
                    for item in sorted(set(default_resource_types + ["reading"]))
                ],
                "mode": "fast_progressive",
            }
        result["plan"] = plan
        trace("PlannerAgent", "completed", "已规划资源主题、难度和目标", int((time.perf_counter() - start) * 1000))
        task_plans = {item["resource_type"]: item for item in plan.get("resource_tasks", [])}

        def resource_types_for_stage(stage: Dict[str, Any]) -> list[str]:
            if use_full_generation:
                return full_resource_types
            types = list(default_resource_types)
            if stage.get("stage_index") == len(stage_specs):
                types.append("reading")
            return types

        stage_material_cache: Dict[str, Dict[str, Any]] = {}

        def prepare_stage_materials(stage: Dict[str, Any]) -> Dict[str, Any]:
            stage_context = self._stage_context(context, stage)
            stage_query = self._build_stage_query(stage, stage_context, query)
            stage_sources = select_profile_knowledge_items(stage_query or query, profile=stage_context, stage=stage, top_k=2)
            if not stage_sources:
                stage_sources = retrieve_knowledge_items(stage_query or query, top_k=2)
            stage_knowledge_context = build_resource_context(stage_query or query, top_k=2, profile=stage_context, stage=stage)
            evidence = self._safe_evidence(stage_sources)
            primary_knowledge = stage_knowledge_context.get("primary_knowledge") or (evidence[0] if evidence else {})
            primary_title = primary_knowledge.get("title") or ""
            stage_context["selected_primary_knowledge_title"] = primary_title
            stage_context["selected_primary_knowledge_content"] = primary_knowledge.get("content") or ""
            stage_context["selected_knowledge_points"] = [item.get("title") for item in evidence if item.get("title")][:3]
            return {
                "stage_context": stage_context,
                "stage_query": stage_query,
                "stage_sources": stage_sources,
                "stage_knowledge_context": stage_knowledge_context,
                "evidence": evidence,
                "primary_knowledge": primary_knowledge,
                "primary_title": primary_title,
                "knowledge_text": self._knowledge_text_for_model(stage_sources, primary_title),
            }

        for stage in stage_specs:
            stage_material_cache[stage.get("stage_id") or str(stage.get("stage_index"))] = prepare_stage_materials(stage)

        def generate_one(resource_type: str, stage: Dict[str, Any]) -> Dict[str, Any]:
            agent = self.resource_agents[resource_type]
            agent_name = agent.__class__.__name__
            cache_key = stage.get("stage_id") or str(stage.get("stage_index"))
            materials = stage_material_cache.get(cache_key) or prepare_stage_materials(stage)
            stage_context = dict(materials["stage_context"])
            emit({"type": "agent", "agent": agent_name, "status": "running", "message": f"正在为{stage.get('stage_title')}生成 {resource_type} 类型资源"})
            started = time.perf_counter()
            task_plan = {
                **task_plans.get(resource_type, {"resource_type": resource_type, "goal": stage_context.get("current_need")}),
                "stage": stage,
                "stage_unique_instruction": stage_context.get("stage_unique_instruction"),
                "goal": stage_context.get("current_need"),
            }
            stage_query = materials["stage_query"]
            stage_sources = materials["stage_sources"]
            stage_knowledge_context = materials["stage_knowledge_context"]
            evidence = materials["evidence"]
            primary_knowledge = materials["primary_knowledge"]
            primary_title = materials["primary_title"]
            stage_context["selected_primary_knowledge_title"] = primary_title
            stage_context["selected_primary_knowledge_content"] = primary_knowledge.get("content") or ""
            stage_context["selected_knowledge_points"] = [item.get("title") for item in evidence if item.get("title")][:3]
            task_plan["selected_primary_knowledge_title"] = primary_title
            task_plan["selected_knowledge_points"] = stage_context["selected_knowledge_points"]
            if not stage_sources:
                logger.warning(
                    "[ResourceAgent] No knowledge sources retrieved, empty resource will be used. resource_type=%s stage_title=%s stage_points=%s query=%s",
                    resource_type,
                    stage.get("stage_title"),
                    stage.get("stage_points") or [],
                    stage_query or query,
                )
                resource = self._empty_resource(resource_type, stage, [])
                quality = {"total": 0, "passed": False, "problems": ["未检索到对应知识库片段"], "checks": {}}
                resource["quality"] = quality
                resource["quality_score"] = 0
                resource["retry_count"] = 0
                resource["stage_id"] = stage.get("stage_id")
                resource["stage_index"] = stage.get("stage_index")
                resource["stage_title"] = stage.get("stage_title")
                resource["stage_points"] = stage.get("stage_points") or []
                resource["metadata"] = {
                    **(resource.get("metadata") or {}),
                    "stage": stage,
                    "evidence": evidence,
                    "debug": {"retrieved_chunks_count": 0},
                }
                resource["sources"] = []
                resource["duration_ms"] = int((time.perf_counter() - started) * 1000)
                return resource

            if use_full_generation:
                resource = agent.generate(stage_context, materials["knowledge_text"], task_plan)
            else:
                resource = self._fast_generate_resource(resource_type, stage_context, materials["knowledge_text"], task_plan)
            emit({"type": "agent", "agent": "QualityAgent", "status": "running", "message": f"正在审核 {agent_name} 生成结果"})
            quality = self.quality_agent.evaluate(resource, stage_context, stage_sources) if use_full_generation else self._fast_quality(resource, stage_sources)
            retries = 0
            if allow_quality_retry and not quality.get("passed"):
                retries = 1
                feedback = "；".join(quality.get("problems") or []) or "请提升准确性、清晰度和个性化程度"
                emit({"type": "agent", "agent": agent_name, "status": "running", "message": f"质量评分未达标，正在根据反馈返工：{feedback}"})
                resource = agent.generate(stage_context, materials["knowledge_text"], task_plan, feedback=feedback)
                emit({"type": "agent", "agent": "QualityAgent", "status": "running", "message": f"正在复审 {agent_name} 返工结果"})
                quality = self.quality_agent.evaluate(resource, stage_context, stage_sources)
            resource["quality"] = quality
            resource["quality_score"] = quality.get("total", 0)
            resource["retry_count"] = retries
            resource["stage_id"] = stage.get("stage_id")
            resource["stage_index"] = stage.get("stage_index")
            resource["stage_title"] = stage.get("stage_title")
            resource["stage_points"] = stage.get("stage_points") or []
            metadata = resource.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            resource["metadata"] = {
                **metadata,
                "stage": stage,
                "primary_knowledge": primary_knowledge,
                "evidence": evidence,
                "learning_location": evidence[0].get("learning_location") if evidence else {},
                "debug": stage_knowledge_context.get("debug", {}),
            }
            resource["sources"] = [
                {"source": item.get("source"), "chunk_index": item.get("chunk_index"), "score": item.get("score"), "retrieval_mode": item.get("retrieval_mode")}
                for item in stage_sources
            ]
            resource["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return resource

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(generate_one, resource_type, stage): (resource_type, stage)
                for stage in stage_specs
                for resource_type in resource_types_for_stage(stage)
            }
            for future in as_completed(futures):
                resource_type, stage = futures[future]
                agent_name = self.resource_agents[resource_type].__class__.__name__
                try:
                    resource = future.result()
                    key = f"{stage.get('stage_id')}:{resource_type}"
                    result["resources"][key] = resource
                    trace(
                        agent_name,
                        "completed" if resource.get("quality", {}).get("passed") else "warning",
                        f"{stage.get('stage_title')} - {resource.get('title', resource_type)} 生成完成，质量评分 {resource.get('quality_score', 0)}",
                        resource.get("duration_ms", 0),
                        resource.get("retry_count", 0),
                    )
                except Exception as exc:
                    result["errors"].append(f"{agent_name} 失败：{exc}")
                    trace(agent_name, "failed", str(exc))
        emit({"type": "agent", "agent": "SafetyAgent", "status": "running", "message": "正在进行内容安全与防幻觉复核"})
        result["resource_list"] = list(result["resources"].values())
        all_content = "\n".join(str(item.get("content") or "") for item in result["resource_list"])
        if use_full_generation:
            result["safety"] = self.safety_agent.review(all_content, sources)
        else:
            result["safety"] = {
                "passed": bool(sources),
                "risk": "未发现明显风险" if sources else "缺少课程知识库依据",
                "sources": sorted({item.get("source", "unknown") for item in sources}),
                "checks": {"fast_local_safety": True, "has_course_sources": bool(sources)},
            }
        trace(
            "SafetyAgent",
            "completed" if result["safety"].get("passed") else "failed",
            result["safety"].get("risk", ""),
        )
        if not result["safety"].get("passed"):
            result["errors"].append(result["safety"].get("risk", "内容安全复核未通过"))
        emit({"type": "agent", "agent": "PackagerAgent", "status": "running", "message": "正在汇总资源包和协作证据"})
        trace("PackagerAgent", "completed", f"已汇总 {len(result['resource_list'])} 类资源")
        emit({"type": "complete", "status": "completed" if not result.get("errors") else "warning", "message": "多智能体资源生成流程已完成", "result": result})
        return result


agent_manager = AgentManager()


