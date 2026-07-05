import json
from typing import Any, Dict

from ai.json_utils import extract_json_object
from ai.rag import build_resource_context, retrieve_knowledge_items
from ai.spark_api import spark_chat
from .base_agent import XunfeiAgentSpec


class TutorAgent:
    """Instant multimodal tutoring agent backed by the local software-engineering KB."""

    def __init__(self):
        self.role = "多模态智能辅导教师"
        self.goal = "基于学生画像和本地软件工程知识库，提供文字解答、图解说明、短视频脚本和针对性学习引导。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["retrieve_knowledge", "spark_chat", "see_dance_generate"],
            input_schema="学生问题 + 学生画像 + 本地知识库上下文",
            output_schema='{"answer":"","diagram":"","video_script":"","self_check":[],"next_actions":[]}',
        )

    def answer(self, question: str, profile: Dict[str, Any] | None = None) -> dict:
        profile = profile or {}
        query = " ".join(
            str(item)
            for item in [
                question,
                profile.get("weak_points"),
                profile.get("study_goal"),
                profile.get("course_progress"),
            ]
            if item
        )
        context = build_resource_context(query or question, top_k=5)
        sources = retrieve_knowledge_items(query or question, top_k=5)
        prompt = f"""
你是软件工程课程的多模态智能辅导教师。请严格依据【本地知识库上下文】回答学生问题。

必须只返回 JSON，不要 Markdown 代码块，不要解释：
{{
  "answer": "详细文字解答，Markdown 格式",
  "diagram": "Mermaid flowchart 图解，以 flowchart LR 开头",
  "video_script": "60 秒以内短视频讲解脚本，包含分镜提示",
  "self_check": ["自测问题1", "自测问题2", "自测问题3"],
  "next_actions": ["下一步学习建议1", "下一步学习建议2"],
  "image_notes": ["配图建议：图片说明（图片路径）"]
}}

输出要求：
1. 文字解答必须包含：问题定位、通俗解释、关键步骤、易错点、一个软件工程场景例子。
2. 图解不能罗列知识点，必须用 flowchart LR 表示概念、流程、判断或因果关系。
3. 如果 images 非空，必须在 answer 和 image_notes 中写出配图建议，保留图片路径。
4. 视频脚本要适合学生快速复习，包含“画面建议 + 旁白 + 字幕要点”。
5. 如果知识库证据不足，必须说明“当前知识库未覆盖”，不能编造。
6. 不要输出 chunk_id、score、retrieval_mode、JSON 字段名。

学生画像：
{json.dumps(profile, ensure_ascii=False, indent=2)}

学生问题：
{question}

本地知识库上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}
""".strip()
        raw = spark_chat(prompt)
        data = extract_json_object(raw)
        if not data:
            data = {
                "answer": raw or "智能辅导生成失败，请检查大模型配置。",
                "diagram": self._fallback_diagram(question),
                "video_script": "当前未能生成稳定的视频脚本，请重新提问或检查大模型配置。",
                "self_check": [],
                "next_actions": [],
                "image_notes": [],
            }
        diagram = str(data.get("diagram") or "").strip()
        if not diagram.lower().startswith(("flowchart", "graph", "mindmap")):
            diagram = self._fallback_diagram(question)
        return {
            "answer": str(data.get("answer") or raw or "智能辅导生成失败，请检查大模型配置。"),
            "diagram": diagram,
            "video_script": str(data.get("video_script") or ""),
            "self_check": data.get("self_check") if isinstance(data.get("self_check"), list) else [],
            "next_actions": data.get("next_actions") if isinstance(data.get("next_actions"), list) else [],
            "image_notes": data.get("image_notes") if isinstance(data.get("image_notes"), list) else [],
            "images": context.get("images", []),
            "evidence": json.dumps(context, ensure_ascii=False),
            "sources": sources,
        }

    @staticmethod
    def _fallback_diagram(question: str) -> str:
        title = str(question or "智能辅导").replace('"', "").replace("[", "").replace("]", "")[:20]
        return "\n".join(
            [
                "flowchart LR",
                f"  A(({title}))",
                "  A --> B[定位问题]",
                "  B --> C[查找知识库]",
                "  C --> D[解释概念]",
                "  D --> E[分析易错点]",
                "  E --> F[给出练习建议]",
            ]
        )
