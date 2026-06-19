from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict

from ai.rag import retrieve_knowledge_items
from ai.spark_api import content_audit
from .code_agent import CodeAgent
from .profile_agent import ProfileAgent
from .quiz_agent import QuizAgent
from .retrieve_agent import RetrieveAgent
from .safety_agent import SafetyAgent
from .text_agent import TextAgent
from .video_agent import VideoAgent
from .visual_agent import VisualAgent


class AgentManager:
    def __init__(self):
        self.profile_agent = ProfileAgent()
        self.retrieve_agent = RetrieveAgent()
        self.text_agent = TextAgent()
        self.quiz_agent = QuizAgent()
        self.visual_agent = VisualAgent()
        self.code_agent = CodeAgent()
        self.video_agent = VideoAgent()
        self.safety_agent = SafetyAgent()

    def run_pipeline(self, dialogue_text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {"profile": {}, "knowledge": "", "sources": [], "resources": {}, "errors": [], "safety": {}}
        if not content_audit(dialogue_text):
            result["errors"].append("学生对话未通过内容审核")
            return result

        try:
            result["profile"] = self.profile_agent.analyze(dialogue_text)
        except Exception as exc:
            result["errors"].append(f"ProfileAgent失败：{exc}")
            result["profile"] = {}

        try:
            result["knowledge"] = self.retrieve_agent.retrieve(result["profile"])
            query = str(result["profile"].get("weak_points") or result["profile"].get("study_goal") or dialogue_text)
            result["sources"] = retrieve_knowledge_items(query, top_k=5)
        except Exception as exc:
            result["errors"].append(f"RetrieveAgent失败：{exc}")
            result["knowledge"] = ""
            result["sources"] = []

        tasks = {
            "text": lambda: self.text_agent.generate(result["profile"], result["knowledge"]),
            "visual": lambda: self.visual_agent.generate(result["knowledge"]),
            "video": lambda: self.video_agent.generate(result["knowledge"]),
        }
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(task): name for name, task in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result["resources"][name] = future.result()
                except Exception as exc:
                    result["errors"].append(f"{name}资源生成失败：{exc}")
                    result["resources"][name] = {}

        text_resources = result["resources"].get("text") or {}
        visual_resources = result["resources"].get("visual") or {}
        video_resource = result["resources"].get("video") or ""
        result["resource_list"] = [
            {"resource_type": "doc", "title": "课程讲解文档", "content": text_resources.get("doc", "")},
            {"resource_type": "quiz", "title": "分难度练习题", "content": text_resources.get("quiz", "")},
            {"resource_type": "reading", "title": "拓展阅读材料", "content": text_resources.get("reading", "")},
            {"resource_type": "mindmap", "title": "知识点思维导图", "content": visual_resources.get("mindmap", "")},
            {"resource_type": "code", "title": "代码实操案例", "content": visual_resources.get("code", "")},
            {"resource_type": "video", "title": "AI教学短视频", "content": video_resource},
        ]
        result["safety"] = self.safety_agent.review(str(result.get("resource_list", "")), result["sources"])
        return result


agent_manager = AgentManager()
