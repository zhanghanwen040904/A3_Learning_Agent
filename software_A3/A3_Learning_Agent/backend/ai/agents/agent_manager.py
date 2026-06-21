import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, Optional

from ai.rag import build_resource_context, retrieve_knowledge_items
from ai.spark_api import content_audit
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

    def run_pipeline(
        self,
        dialogue_text: str = "",
        stored_profile: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
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

        def trace(agent: str, status: str, message: str, duration_ms: int = 0, retry_count: int = 0) -> None:
            result["trace"].append(
                {
                    "agent": agent,
                    "status": status,
                    "message": message,
                    "duration_ms": duration_ms,
                    "retry_count": retry_count,
                    "time": self._now(),
                }
            )

        if dialogue_text and not content_audit(dialogue_text):
            result["errors"].append("学生输入未通过内容审核")
            trace("SafetyAgent", "failed", "学生输入未通过内容审核")
            return result

        start = time.perf_counter()
        context = self._build_context(dialogue_text, stored_profile, request_data)
        result["context"] = context
        result["profile"] = {field: context.get(field) for field in self.PROFILE_FIELDS}
        trace("ProfileAgent", "completed", "已读取结构化画像并合并本次学习需求", int((time.perf_counter() - start) * 1000))

        start = time.perf_counter()
        query = self._build_query(dialogue_text, context)
        knowledge_context = build_resource_context(query, top_k=6)
        sources = retrieve_knowledge_items(query, top_k=6)
        result["knowledge_context"] = knowledge_context
        result["sources"] = sources
        result["knowledge"] = json.dumps(knowledge_context, ensure_ascii=False, indent=2)
        trace("RetrieveAgent", "completed" if sources else "warning", f"召回 {len(sources)} 个本地知识库片段", int((time.perf_counter() - start) * 1000))

        start = time.perf_counter()
        plan = self.planner_agent.plan(context, sources)
        result["plan"] = plan
        trace("PlannerAgent", "completed", "已规划六类互补资源的主题、难度和目标", int((time.perf_counter() - start) * 1000))
        task_plans = {item["resource_type"]: item for item in plan.get("resource_tasks", [])}

        def generate_one(resource_type: str) -> Dict[str, Any]:
            agent = self.resource_agents[resource_type]
            started = time.perf_counter()
            task_plan = task_plans.get(resource_type, {"resource_type": resource_type, "goal": context.get("current_need")})
            resource = agent.generate(context, result["knowledge"], task_plan)
            quality = self.quality_agent.evaluate(resource, context, sources)
            retries = 0
            if not quality.get("passed"):
                retries = 1
                feedback = "；".join(quality.get("problems") or []) or "请提升准确性、清晰度和个性化程度"
                resource = agent.generate(context, result["knowledge"], task_plan, feedback=feedback)
                quality = self.quality_agent.evaluate(resource, context, sources)
            resource["quality"] = quality
            resource["quality_score"] = quality.get("total", 0)
            resource["retry_count"] = retries
            resource["sources"] = [
                {
                    "source": item.get("source"),
                    "chunk_index": item.get("chunk_index"),
                    "score": item.get("score"),
                    "retrieval_mode": item.get("retrieval_mode"),
                }
                for item in sources
            ]
            resource["duration_ms"] = int((time.perf_counter() - started) * 1000)
            return resource

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(generate_one, resource_type): resource_type
                for resource_type in self.resource_agents
            }
            for future in as_completed(futures):
                resource_type = futures[future]
                agent_name = self.resource_agents[resource_type].__class__.__name__
                try:
                    resource = future.result()
                    result["resources"][resource_type] = resource
                    trace(
                        agent_name,
                        "completed" if resource.get("quality", {}).get("passed") else "warning",
                        f"{resource.get('title', resource_type)} 生成完成，质量评分 {resource.get('quality_score', 0)}",
                        resource.get("duration_ms", 0),
                        resource.get("retry_count", 0),
                    )
                except Exception as exc:
                    result["errors"].append(f"{agent_name} 失败：{exc}")
                    trace(agent_name, "failed", str(exc))

        result["resource_list"] = [result["resources"][key] for key in self.resource_agents if key in result["resources"]]
        all_content = "\n".join(str(item.get("content") or "") for item in result["resource_list"])
        result["safety"] = self.safety_agent.review(all_content, sources)
        trace(
            "SafetyAgent",
            "completed" if result["safety"].get("passed") else "failed",
            result["safety"].get("risk", ""),
        )
        if not result["safety"].get("passed"):
            result["errors"].append(result["safety"].get("risk", "内容安全复核未通过"))
        trace("PackagerAgent", "completed", f"已汇总 {len(result['resource_list'])} 类资源")
        return result


agent_manager = AgentManager()
