import json
from typing import Any, Dict, List

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.llm_adapter import PlatformLLM
from ai.langchain_parsers import parse_json_with_fallback
from .base_agent import AgentSpec


def build_langchain_chain(prompt: Any) -> Any:
    if prompt is None or LangChainStrOutputParser is None:
        return None
    return prompt | PlatformLLM() | LangChainStrOutputParser()


RESOURCE_PROMPT_TEMPLATE = """
[RESOURCE:{resource_type}]
你是{role}。目标：{goal}
请只生成你负责的“{raw_resource_type}”资源，不要代替其他智能体。

【学生个性化上下文】
{context}

【阶段专属要求】
必须严格围绕上下文中的 stage_index、stage_title、stage_goal、stage_points 与 stage_unique_instruction 生成；不要把其他阶段内容混入当前资源。

【PlannerAgent任务计划】
{task_plan}

【课程知识库依据】
{knowledge_text}

【本资源质量要求】
{requirements}

【上一轮审核意见】
{feedback}

必须严格返回JSON，不要使用Markdown代码围栏：
{{"title":"资源标题","content":"完整资源内容","knowledge_points":["知识点"],"personalization":"明确说明如何依据该学生的专业、短板、目标和偏好进行调整","format":"markdown"}}
""".strip()

RESOURCE_PROMPT = LangChainPromptTemplate.from_template(RESOURCE_PROMPT_TEMPLATE) if LangChainPromptTemplate is not None else None


class StructuredResourceAgent:
    """六类资源智能体的公共协议，统一输入输出但保留独立角色与提示词。"""

    resource_type = "unknown"
    role = "学习资源生成师"
    goal = "生成个性化学习资源"
    requirements = "内容准确、清晰并适合学生当前水平。"
    default_title = "个性化学习资源"

    def __init__(self):
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["langchain_prompt", "platform_llm", "retrieve_knowledge"],
            input_schema="结构化学生画像 + 资源规划 + RAG教材片段 + 可选返工意见",
            output_schema=(
                '{"title":"","content":"","knowledge_points":[],"personalization":"",'
                '"format":"markdown"}'
            ),
        )
        self.chain = build_langchain_chain(RESOURCE_PROMPT)

    @staticmethod
    def _is_model_error(raw: str) -> bool:
        text = str(raw or "")
        if "调用失败" in text or "AppIdNoAuthError" in text or "NoAuth" in text:
            return True
        try:
            data = json.loads(text)
        except Exception:
            return False
        return isinstance(data, dict) and data.get("success") is False

    def _fallback_resource(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
    ) -> Dict[str, Any]:
        weak_points = (
            context.get("weak_points")
            or context.get("error_prone_points")
            or context.get("study_goal")
            or "课程核心知识"
        )
        points = self._context_points(context)
        excerpt = str(knowledge_text or "").strip()[:420]
        if not excerpt:
            excerpt = "请结合课程知识库中的对应章节，按概念、流程、案例和练习逐步学习。"
        content = f"""# {self.default_title}

## 学习目标
围绕“{weak_points}”完成本阶段学习，先理解核心概念，再通过案例和练习巩固。

## 课程依据
{excerpt}

## 学习建议
- 先阅读阶段目标，明确本资源解决的问题。
- 对照知识点梳理输入、过程、输出和常见误区。
- 结合练习题、图解或代码案例完成迁移应用。

## 自测任务
请用自己的话说明本阶段核心概念，并举出一个软件工程课程中的应用场景。"""
        return {
            "resource_type": self.resource_type,
            "title": self.default_title,
            "content": content,
            "knowledge_points": points,
            "personalization": (
                f"围绕学生薄弱点“{weak_points}”，结合课程知识库内容进行兜底组织，"
                "避免展示模型接口错误。"
            ),
            "format": "markdown",
            "agent_name": self.__class__.__name__,
        }

    def _fallback_doc_resource(self, context: Dict[str, Any], knowledge_text: str) -> Dict[str, Any]:
        stage_title = str(context.get("stage_title") or "").strip()
        points = [str(item) for item in (self._context_points(context) or [stage_title or "软件工程核心知识"]) if str(item).strip()]
        if not points:
            points = ["软件工程核心知识"]
        topic = stage_title or "、".join(points[:3])
        excerpt = str(knowledge_text or "").strip()[:520] or "课程知识库暂未提供足够片段，请结合教材相关章节理解概念、流程、案例和常见误区。"
        explanations = []
        for point in points[:3]:
            explanations.append({
                "title": point,
                "explanation": f"{point}是本阶段需要重点理解的知识点。学习时不能只记住名称，而要把它放到软件工程过程里理解：它解决什么问题、依赖什么输入、产生什么输出、会影响哪些后续活动。结合课程知识库内容可知：{excerpt}。在实际项目中，{point}通常会与需求、设计、实现、测试或维护活动发生关联，因此要从概念、流程和产物三个角度掌握。",
                "process": ["明确概念边界", "分析输入信息", "理解处理过程", "识别输出产物"],
                "input_output": {"input": "课程案例、需求描述、设计或实现信息", "output": "概念理解、阶段产物或质量判断"},
                "example": f"以课程中的软件项目为例，可以用{point}分析项目在当前阶段需要完成的任务和可能出现的质量风险。",
                "exam_focus": "常考概念定义、作用、流程顺序、输入输出和相近概念辨析。",
            })
        content = {
            "resourcetype": "doc",
            "resourcetitle": f"{topic}讲解文档",
            "knowledgelevel": context.get("knowledge_level") or "待观察",
            "studystyle": context.get("study_style") or "综合学习",
            "weakpoints": points,
            "studygoal": context.get("study_goal") or f"理解{topic}相关知识",
            "studytimepreferred": context.get("study_time_preferred") or "25分钟",
            "courseprogress": context.get("course_progress") or "当前阶段",
            "estimatedtime": "25分钟",
            "challengescene": "从概念记忆过渡到案例分析和阶段测评应用",
            "preferredresourcetype": "doc",
            "profilesummary": {
                "major": context.get("major") or "未填写",
                "minor": context.get("minor") or "未填写",
                "weakpoint": topic,
                "studygoal": context.get("study_goal") or f"掌握{topic}",
            },
            "studentcontext": {
                "currentclass": context.get("current_class") or "软件工程",
                "currentunit": context.get("current_unit") or "当前单元",
                "currentchapter": context.get("current_chapter") or "当前章节",
                "currentsection": context.get("current_section") or "当前小节",
                "currentpage": context.get("current_page") or "",
            },
            "overview": {
                "title": "本阶段学习导入",
                "content": f"本阶段围绕{topic}展开。学习这些内容的目的，是帮助你理解软件工程活动为什么要按阶段、按流程、按质量标准推进。掌握本阶段后，你应该能够说清楚核心概念的含义，判断它在软件生命周期中的位置，并能结合课程案例分析输入、过程、输出和常见风险。",
            },
            "core_concepts": [
                {"name": point, "definition": f"{point}是软件工程课程中的关键概念，需要结合项目活动理解。", "why_it_matters": "它影响后续阶段的质量、沟通和决策。", "example": f"在课程项目中，可用{point}分析当前阶段任务。", "common_misunderstanding": "只背定义，不理解适用场景和产物。"}
                for point in points[:3]
            ],
            "knowledge_explanation": explanations,
            "lifecycle_position": {
                "phase": "当前学习阶段",
                "before": "前置概念、需求或设计信息",
                "after": "后续实现、测试、维护和质量评估",
                "connection": f"{topic}不是孤立知识点，它会连接软件生命周期中的前后活动。理解上下游关系，有助于判断为什么某个阶段产物会影响后续质量。",
            },
            "case_study": {
                "title": "课程项目案例分析",
                "scenario": "假设团队正在开发一个在线学习系统，需要从需求理解、功能设计到测试验证逐步推进。",
                "analysis": f"在这个场景中，{topic}可以帮助团队明确当前阶段的关键任务。如果只停留在口头理解，很容易出现需求边界不清、设计依据不足或测试目标模糊等问题。通过把知识点转化为输入、活动和输出，学生可以更清楚地看到每个软件工程活动的价值，也能在阶段测评中更准确地区分概念、流程和产物。",
                "takeaway": "学习软件工程知识时，要始终追问它解决什么问题、输出什么产物、会影响哪些后续环节。",
            },
            "mistakes": [
                {"mistake": "只记概念名称", "reason": "没有结合项目流程", "correction": "从作用、输入输出和案例三个角度理解", "example": "解释一个概念时同时说明它会产生什么阶段产物。"},
                {"mistake": "混淆相近概念", "reason": "没有比较适用场景", "correction": "通过边界、目标和产物进行区分", "example": "区分测试与调试、需求与设计等概念。"},
                {"mistake": "忽略后续影响", "reason": "只看当前阶段", "correction": "分析它对后续实现、测试或维护的影响", "example": "需求不清会导致测试用例难以设计。"},
            ],
            "learning_path": ["先阅读本阶段导入，理解学习目标", "再逐个学习核心概念和详细讲解", "结合案例分析输入、过程和输出", "最后完成自测问题并进入阶段评估"],
            "summary": {"key_takeaways": [f"{topic}需要结合软件生命周期理解", "学习重点是概念、流程、产物和易错点", "通过案例和自测可以检验迁移应用能力"], "one_sentence": f"本阶段的核心是把{topic}从概念记忆转化为软件工程场景中的应用能力。"},
            "self_check": [
                {"question": f"请说明{points[0]}解决什么问题？", "hint": "从目标、输入和输出角度回答。"},
                {"question": "本阶段知识点会影响哪些后续阶段？", "hint": "联系设计、测试、维护或质量评估。"},
                {"question": "举一个课程案例说明本阶段知识点的作用。", "hint": "用一个软件项目场景说明。"},
            ],
            "learningresources": [{"title": f"{topic}课程知识库片段", "source": "课程知识库", "sectionpath": context.get("course_progress") or "当前章节", "pages": "", "chunkid": "fallback-doc", "content": excerpt, "images": []}],
        }
        return {
            "resource_type": self.resource_type,
            "title": content["resourcetitle"],
            "content": json.dumps(content, ensure_ascii=False, indent=2),
            "knowledge_points": points,
            "personalization": f"围绕学生薄弱点“{topic}”生成教学型结构化讲解，补充概念、案例、易错点和自测问题。",
            "format": "json",
            "agent_name": self.__class__.__name__,
        }

    @staticmethod
    def _is_doc_content_weak(content: Any) -> bool:
        if not isinstance(content, dict):
            return True
        explanations = content.get("knowledge_explanation") or []
        concepts = content.get("core_concepts") or []
        return len(explanations) < 2 or len(concepts) < 2 or not content.get("case_study") or not content.get("mistakes")

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        variables = {
            "resource_type": self.resource_type.upper(),
            "raw_resource_type": self.resource_type,
            "role": self.role,
            "goal": self.goal,
            "context": json.dumps(context, ensure_ascii=False),
            "task_plan": json.dumps(task_plan, ensure_ascii=False),
            "knowledge_text": knowledge_text,
            "requirements": self.requirements,
            "feedback": feedback or "首次生成，无返工意见",
        }
        if self.chain is not None:
            raw = self.chain.invoke(variables)
        else:
            raw = PlatformLLM().invoke(RESOURCE_PROMPT_TEMPLATE.format(**variables))
        if self._is_model_error(raw):
            if self.resource_type == "doc":
                return self._fallback_doc_resource(context, knowledge_text)
            return self._fallback_resource(context, knowledge_text)
        data = parse_json_with_fallback(raw)
        if self.resource_type == "doc" and data.get("resourcetype"):
            data = {
                "title": data.get("resourcetitle") or data.get("title") or self.default_title,
                "content": data,
                "knowledge_points": data.get("weakpoints") or self._context_points(context),
                "personalization": "依据学生画像、学习目标与课程知识库片段生成结构化讲解文档。",
                "format": "json",
            }
        if self.resource_type == "doc" and self._is_doc_content_weak(data.get("content")):
            return self._fallback_doc_resource(context, knowledge_text)
        content_value = data.get("content") or raw or "资源生成失败"
        content = json.dumps(content_value, ensure_ascii=False, indent=2) if isinstance(content_value, (dict, list)) else str(content_value)
        points = data.get("knowledge_points") or self._context_points(context)
        if not isinstance(points, list):
            points = [str(points)]
        return {
            "resource_type": self.resource_type,
            "title": str(data.get("title") or self.default_title),
            "content": content,
            "knowledge_points": [str(item) for item in points if str(item).strip()],
            "personalization": str(
                data.get("personalization")
                or (
                    f"围绕学生薄弱点“{context.get('weak_points', '待观察')}”，"
                    f"按其学习偏好“{context.get('study_style', '综合学习')}”组织内容。"
                )
            ),
            "format": str(data.get("format") or "markdown"),
            "agent_name": self.__class__.__name__,
        }

    @staticmethod
    def _context_points(context: Dict[str, Any]) -> List[str]:
        value = context.get("weak_points") or context.get("study_goal") or "课程核心知识"
        if isinstance(value, list):
            return value[:4]
        return [item.strip() for item in str(value).replace("，", ",").split(",") if item.strip()][:4]
