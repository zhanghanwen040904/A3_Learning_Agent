import ast
import re
from typing import Any, Dict, List

from ai.spark_api import content_audit
from .base_agent import XunfeiAgentSpec


class QualityAgent:
    """对准确性、个性化、完整性和来源支撑进行可解释评分。"""

    def __init__(self):
        self.role = "学习资源质量评估师"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal="量化评估资源质量并提出可执行返工意见",
            tools=["content_audit", "retrieve_knowledge"],
            input_schema="生成资源 + 学生上下文 + RAG来源",
            output_schema="四维评分 + 是否通过 + 问题列表",
        )

    def evaluate(self, resource: Dict[str, Any], context: Dict[str, Any], sources: List[dict]) -> Dict[str, Any]:
        content = str(resource.get("content") or "")
        resource_type = resource.get("resource_type")
        min_length = {"doc": 220, "quiz": 220, "reading": 180, "mindmap": 80, "code": 180, "video": 180}.get(resource_type, 120)
        completeness = min(100, 55 + int(len(content) / max(min_length, 1) * 45)) if content else 0
        personalization = 90 if resource.get("personalization") and context.get("weak_points") else 60
        source_support = 90 if sources else 35
        format_ok = True
        code_syntax_ok = None
        problems = []
        if len(content) < min_length:
            problems.append(f"内容偏短，建议不少于{min_length}字符")
        if resource_type == "mindmap" and not content.lstrip().startswith("mindmap"):
            format_ok = False
            problems.append("思维导图不是合法的Mermaid mindmap源码")
        if resource_type == "code":
            fenced = re.search(r"```python\s*([\s\S]*?)```", content, flags=re.IGNORECASE)
            code = fenced.group(1) if fenced else content if "import " in content else ""
            if not code:
                format_ok = False
                code_syntax_ok = False
                problems.append("代码资源缺少可识别的Python代码主体")
            else:
                try:
                    ast.parse(code)
                    code_syntax_ok = True
                except SyntaxError as exc:
                    format_ok = False
                    code_syntax_ok = False
                    problems.append(f"Python语法检查失败：第{exc.lineno}行")
        if not sources:
            problems.append("缺少课程知识库来源")
        if not content_audit(content):
            format_ok = False
            problems.append("内容安全审核未通过")
        accuracy = 90 if sources and format_ok else 60
        total = round(accuracy * 0.35 + personalization * 0.25 + completeness * 0.25 + source_support * 0.15)
        passed = total >= 75 and format_ok and bool(sources)
        return {
            "accuracy": accuracy,
            "personalization": personalization,
            "completeness": completeness,
            "source_support": source_support,
            "total": total,
            "passed": passed,
            "problems": problems,
            "checks": {"content_audit": content_audit(content), "code_syntax_ok": code_syntax_ok},
        }
