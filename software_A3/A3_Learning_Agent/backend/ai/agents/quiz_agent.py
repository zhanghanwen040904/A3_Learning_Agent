from typing import Any, Dict, List

from ..assessment_pipeline import generate_personalized_questions
from .resource_base import StructuredResourceAgent


class QuizAgent(StructuredResourceAgent):
    resource_type = "quiz"
    role = "分层多题型练习设计师"
    goal = "针对学生短板设计可诊断、可反馈的分层练习"
    default_title = "个性化分层练习题"
    requirements = (
        "优先使用真实题库，覆盖基础、提升、应用层。"
        "每题标注难度、关联知识点、答案和解析。"
    )

    @staticmethod
    def _normalize_mastery(context: Dict[str, Any]) -> List[dict]:
        weak_points = context.get("weak_points") or []
        if isinstance(weak_points, str):
            weak_points = [item.strip() for item in weak_points.replace("，", "、").split("、") if item.strip()]
        records = []
        for item in weak_points[:8]:
            records.append({"knowledge_point": item, "mastery_score": 55})
        return records

    @staticmethod
    def _format_question(index: int, item: Dict[str, Any]) -> str:
        main_titles = item.get("primary_knowledge_titles") or item.get("related_knowledge_titles") or [item.get("knowledge_point") or "未标注"]
        lines = [
            f"### 第{index}题",
            f"- 题型：{item.get('question_type') or '未标注'}",
            f"- 难度：{item.get('difficulty') or item.get('difficulty_level') or 'basic'}",
            f"- 主知识点：{'、'.join(main_titles)}",
        ]
        prereq = item.get("prerequisite_knowledge_titles") or []
        if prereq:
            lines.append(f"- 前置知识点：{'、'.join(prereq)}")
        lines.append("")
        lines.append(f"题目：{item.get('stem') or item.get('prompt') or item.get('content') or ''}")

        options = item.get("options") or []
        if options:
            lines.append("")
            lines.extend([str(opt) for opt in options])

        answer = str(item.get("reference_answer") or item.get("answer") or "").strip()
        explanation = str(item.get("explanation") or item.get("analysis") or "").strip()
        if answer:
            lines.append("")
            lines.append(f"答案：{answer}")
        if explanation:
            lines.append(f"解析：{explanation}")
        return "\n".join(lines)

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        stage_index = task_plan.get("stage_index")
        stage_title = str(task_plan.get("stage_title") or context.get("study_goal") or "当前阶段")
        stage_points = task_plan.get("stage_points") or []
        target = stage_points[0] if stage_points else str(context.get("current_need") or "")

        quiz_result = generate_personalized_questions(
            profile=context,
            mastery_records=self._normalize_mastery(context),
            count=5,
            knowledge_point=target,
            knowledge_points=stage_points,
            stage_index=stage_index,
            stage_title=stage_title,
        )
        questions = quiz_result.get("questions") or []
        if not questions:
            return super().generate(context, knowledge_text, task_plan, feedback)

        focus_points = quiz_result.get("focus_points") or stage_points or ([target] if target else [])
        content_blocks = [
            f"# {stage_title}练习题",
            "",
            f"本套题优先来自真实题库，聚焦：{'、'.join(focus_points)}",
            "",
        ]
        for index, item in enumerate(questions, start=1):
            content_blocks.append(self._format_question(index, item))
            content_blocks.append("")

        return {
            "resource_type": self.resource_type,
            "title": f"{stage_title}练习题",
            "content": "\n".join(content_blocks).strip(),
            "knowledge_points": quiz_result.get("recommended_knowledge_points") or stage_points,
            "personalization": "已优先使用真实题库，并按当前阶段知识点与学生薄弱项筛题。",
            "format": "markdown",
            "agent_name": self.__class__.__name__,
            "metadata": {
                "question_count": len(questions),
                "recommended_knowledge_points": quiz_result.get("recommended_knowledge_points") or [],
                "bank_source": "questions_json",
            },
        }
