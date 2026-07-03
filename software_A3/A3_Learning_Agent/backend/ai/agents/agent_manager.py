import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, Optional, List

from ai.rag import build_resource_context, retrieve_knowledge_items
from ai.llm_api import audit_content
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
            stages.append({"stage_index": index + 1, "stage_id": f"stage_{index + 1}", "stage_title": title, "stage_goal": stage_goal, "stage_points": stage_points})
        if stages:
            return stages[:4]
        points = self._extract_stage_points(" ".join(str(context.get(key) or "") for key in ["weak_points", "study_goal", "current_need"]))
        return [
            {"stage_index": 1, "stage_id": "stage_1", "stage_title": "基础概念澄清", "stage_goal": "理解核心概念、阶段产物和输入输出关系。", "stage_points": points[:2] or points},
            {"stage_index": 2, "stage_id": "stage_2", "stage_title": "方法关系建构", "stage_goal": "建立相关方法、流程和阶段之间的关系。", "stage_points": points},
            {"stage_index": 3, "stage_id": "stage_3", "stage_title": "练习与应用巩固", "stage_goal": "通过练习、案例和应用任务完成迁移。", "stage_points": points},
        ]

    def _stage_context(self, context: Dict[str, Any], stage: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(context)
        merged.update(stage)
        merged["weak_points"] = stage.get("stage_points") or context.get("weak_points")
        merged["study_goal"] = f"{stage.get('stage_title')}：{stage.get('stage_goal')}"
        merged["current_need"] = (
            f"只生成第{stage.get('stage_index')}阶段《{stage.get('stage_title')}》的资源。"
            f"本阶段目标：{stage.get('stage_goal')}。"
            f"本阶段知识点：{'、'.join(stage.get('stage_points') or [])}。"
            "不要复述其他阶段目标，不要把整条学习路径合并成通用内容。"
        )
        merged["stage_unique_instruction"] = (
            f"当前资源必须突出第{stage.get('stage_index')}阶段，与其他阶段区分开："
            f"标题、案例、讲解重点、自测问题都要围绕《{stage.get('stage_title')}》。"
        )
        return merged

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
        knowledge_context = build_resource_context(query, top_k=6)
        sources = retrieve_knowledge_items(query, top_k=6)
        result["knowledge_context"] = knowledge_context
        result["sources"] = sources
        result["knowledge"] = json.dumps(knowledge_context, ensure_ascii=False, indent=2)
        trace("RetrieveAgent", "completed" if sources else "warning", f"召回 {len(sources)} 个本地知识库片段", int((time.perf_counter() - start) * 1000))

        emit({"type": "agent", "agent": "PlannerAgent", "status": "running", "message": "正在规划六类互补资源的主题、难度和目标"})
        start = time.perf_counter()
        plan = self.planner_agent.plan(context, sources)
        result["plan"] = plan
        trace("PlannerAgent", "completed", "已规划六类互补资源的主题、难度和目标", int((time.perf_counter() - start) * 1000))
        task_plans = {item["resource_type"]: item for item in plan.get("resource_tasks", [])}
        stage_specs = self._parse_stage_specs((request_data or {}).get("path_content") or "", context)
        default_resource_types = ["doc", "mindmap"]
        full_resource_types = list(self.resource_agents.keys())
        use_full_generation = bool((request_data or {}).get("full_generation"))
        allow_quality_retry = use_full_generation

        def resource_types_for_stage(stage: Dict[str, Any]) -> list[str]:
            if use_full_generation:
                return full_resource_types
            types = list(default_resource_types)
            if stage.get("stage_index") == len(stage_specs):
                types.append("reading")
            return types

        def generate_one(resource_type: str, stage: Dict[str, Any]) -> Dict[str, Any]:
            agent = self.resource_agents[resource_type]
            agent_name = agent.__class__.__name__
            stage_context = self._stage_context(context, stage)
            emit({"type": "agent", "agent": agent_name, "status": "running", "message": f"正在为{stage.get('stage_title')}生成 {resource_type} 类型资源"})
            started = time.perf_counter()
            task_plan = {
                **task_plans.get(resource_type, {"resource_type": resource_type, "goal": stage_context.get("current_need")}),
                "stage": stage,
                "stage_unique_instruction": stage_context.get("stage_unique_instruction"),
                "goal": stage_context.get("current_need"),
            }
            stage_query = " ".join([stage.get("stage_title", ""), stage.get("stage_goal", ""), " ".join(stage.get("stage_points") or [])])
            stage_knowledge_context = build_resource_context(stage_query or query, top_k=6)
            stage_sources = retrieve_knowledge_items(stage_query or query, top_k=6)
            resource = agent.generate(stage_context, json.dumps(stage_knowledge_context, ensure_ascii=False, indent=2), task_plan)
            emit({"type": "agent", "agent": "QualityAgent", "status": "running", "message": f"正在审核 {agent_name} 生成结果"})
            quality = self.quality_agent.evaluate(resource, stage_context, stage_sources)
            retries = 0
            if allow_quality_retry and not quality.get("passed"):
                retries = 1
                feedback = "；".join(quality.get("problems") or []) or "请提升准确性、清晰度和个性化程度"
                emit({"type": "agent", "agent": agent_name, "status": "running", "message": f"质量评分未达标，正在根据反馈返工：{feedback}"})
                resource = agent.generate(stage_context, json.dumps(stage_knowledge_context, ensure_ascii=False, indent=2), task_plan, feedback=feedback)
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
            resource["metadata"] = {**metadata, "stage": stage}
            resource["sources"] = [
                {"source": item.get("source"), "chunk_index": item.get("chunk_index"), "score": item.get("score"), "retrieval_mode": item.get("retrieval_mode")}
                for item in stage_sources
            ]
            resource["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return resource

        with ThreadPoolExecutor(max_workers=3) as executor:
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
        result["safety"] = self.safety_agent.review(all_content, sources)
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
