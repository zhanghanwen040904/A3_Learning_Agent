import json
import logging
import re
from typing import Any, Dict, List, Tuple

try:
    from langchain_core.output_parsers import StrOutputParser as LangChainStrOutputParser
    from langchain_core.prompts import PromptTemplate as LangChainPromptTemplate
except ModuleNotFoundError:
    LangChainStrOutputParser = None
    LangChainPromptTemplate = None

from ai.llm_adapter import PlatformLLM
from ai.langchain_parsers import parse_json_with_fallback
from .base_agent import AgentSpec


logger = logging.getLogger(__name__)


FORBIDDEN_LABEL_RE = re.compile(
    r"(标题|章节路径|页码|内容|教材依据|教材片段重点说明|结合课程知识库内容可知|主知识点|补充知识点|教材内容)\s*[：:]\s*"
)


RESOURCE_PROMPT_TEMPLATE = """
[RESOURCE:{resource_type}]
你是{role}。你的目标是：{goal}

学生画像与本次学习需求：
{context}

当前阶段任务规划：
{task_plan}

课程知识依据：
{knowledge_text}

资源质量要求：
{requirements}

如果有上一轮返工意见，请优先修正：
{feedback}

只返回 JSON，不要输出 Markdown 代码块，不要输出解释性前缀。
返回格式如下：
{{
  "title": "资源标题",
  "content": "完整资源内容",
  "knowledge_points": ["知识点1", "知识点2"],
  "personalization": "说明如何结合学生画像进行了调整",
  "format": "markdown"
}}
""".strip()


RESOURCE_PROMPT = (
    LangChainPromptTemplate.from_template(RESOURCE_PROMPT_TEMPLATE)
    if LangChainPromptTemplate is not None
    else None
)


def build_langchain_chain(prompt: Any) -> Any:
    if prompt is None or LangChainStrOutputParser is None:
        return None
    return prompt | PlatformLLM() | LangChainStrOutputParser()


def _strip_labels(text: Any) -> str:
    value = str(text or "").replace("\\n", " ")
    value = FORBIDDEN_LABEL_RE.sub("", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ，。；;:：")


class StructuredResourceAgent:
    resource_type = "unknown"
    role = "学习资源生成助手"
    goal = "生成个性化学习资源"
    requirements = "内容准确、清晰，并且适合学生当前水平。"
    default_title = "个性化学习资源"

    def __init__(self):
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["langchain_prompt", "spark_llm", "retrieve_knowledge"],
            input_schema="结构化学生画像 + 资源规划 + 教材知识片段 + 可选返工意见",
            output_schema='{"title":"","content":"","knowledge_points":[],"personalization":"","format":"markdown"}',

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

    @staticmethod
    def _context_points(context: Dict[str, Any]) -> List[str]:
        value = (
            context.get("selected_knowledge_points")
            or context.get("weak_points")
            or context.get("study_goal")
            or "课程核心知识"
        )
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:4]
        return [item.strip() for item in re.split(r"[，,；;]", str(value)) if item.strip()][:4]

    @staticmethod
    def _sentence_list(text: str) -> List[str]:
        return [item.strip() for item in re.split(r"[。！？!?]", str(text or "")) if item.strip()]

    @staticmethod
    def _normalize_title(text: Any) -> str:
        return re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]+", "", str(text or "").lower())

    @classmethod
    def _extract_primary_basis(cls, knowledge_text: str) -> Tuple[str, str, List[str]]:
        raw = str(knowledge_text or "").strip()
        if not raw or raw == "未检索到对应知识库片段。":
            return "课程核心知识", "", []

        main_title = "课程核心知识"
        main_match = re.search(r"主知识点\s*[：:]\s*(.+)", raw)
        if main_match:
            main_title = _strip_labels(main_match.group(1)) or main_title

        support_titles: List[str] = []
        for match in re.finditer(r"补充知识点\s*[：:]\s*(.+)", raw):
            title = _strip_labels(match.group(1))
            if title and title != main_title and title not in support_titles:
                support_titles.append(title)

        lines: List[str] = []
        for raw_line in raw.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("主知识点") or line.startswith("补充知识点"):
                continue
            if line.startswith("教材内容"):
                line = line.split("：", 1)[-1].strip()
            cleaned = _strip_labels(line)
            if cleaned:
                lines.append(cleaned)
        basis_text = " ".join(lines)
        basis_text = re.sub(r"\s{2,}", " ", basis_text).strip()
        return main_title, basis_text[:1600], support_titles[:2]

    @classmethod
    def _pick_fact(cls, facts: List[str], keywords: List[str]) -> str:
        for sentence in facts:
            if any(keyword in sentence for keyword in keywords):
                return sentence
        return ""

    @classmethod
    def _build_basis_summary(cls, basis_text: str, limit: int = 2) -> str:
        facts = cls._sentence_list(basis_text)
        return "；".join(facts[:limit]) if facts else ""

    @staticmethod
    def _is_requirement_analysis(title: str) -> bool:
        return "需求分析" in str(title or "")

    def _fallback_resource(self, context: Dict[str, Any], knowledge_text: str) -> Dict[str, Any]:
        points = self._context_points(context)
        title = str(context.get("stage_title") or self.default_title).strip() or self.default_title
        basis = self._build_basis_summary(_strip_labels(knowledge_text), limit=2) or "未检索到足够教材片段，建议补充知识库后重新生成。"
        content = (
            f"# {title}\n\n"
            f"## 学习目标\n围绕 {points[0] if points else '课程核心知识'} 建立阶段理解，重点弄清它在软件工程流程中的位置、作用和后续影响。\n\n"
            f"## 教材依据\n{basis}\n\n"
            f"## 学习建议\n"
            f"- 先明确阶段位置。\n"
            f"- 再梳理输入、处理过程和输出。\n"
            f"- 最后结合项目场景判断它如何影响后续工作。"
        )
        return {
            "resource_type": self.resource_type,
            "title": title,
            "content": content,
            "knowledge_points": points,
            "personalization": "已根据学生当前阶段和知识短板组织内容。",
            "format": "markdown",
            "agent_name": self.__class__.__name__,
        }

    def _build_requirement_explanation(self, basis_text: str) -> str:
        facts = self._sentence_list(basis_text)
        phase_hint = self._pick_fact(facts, ["软件定义"])
        step_hint = self._pick_fact(facts, ["问题定义", "可行性研究", "需求分析"])
        task_hint = self._pick_fact(facts, ["目标系统", "需求"])
        artifact_hint = self._pick_fact(facts, ["规格说明书", "数据流图", "数据字典", "逻辑模型"])
        impact_hint = self._pick_fact(facts, ["设计", "实现", "测试"])

        p1 = (
            "需求分析处在软件定义阶段。这个阶段通常先明确项目到底要解决什么问题，再判断方案是否值得做、能否做，"
            "最后把用户真正需要的系统能力表达清楚。因此，需求分析并不是单独的一步，而是软件定义阶段中承上启下的关键环节。"
        )
        if phase_hint:
            p1 += f" 教材中也强调了这一点：{phase_hint}。"
        if step_hint:
            p1 += f" 从阶段顺序看，相关步骤可以概括为：{step_hint}。"

        p2 = (
            "这一环节的核心任务，是回答“目标系统必须做什么”。分析人员需要持续与用户沟通，澄清业务流程、功能边界、"
            "数据要求以及约束条件，把模糊的想法整理成可以确认的需求。它关注的重点不是怎么实现，而是系统应该具备哪些功能，"
            "以及这些功能在什么条件下成立。"
        )
        if task_hint:
            p2 += f" 教材片段中与这一任务最直接对应的表述是：{task_hint}。"

        p3 = (
            "从输入和输出看，需求分析以前面的项目目标、可行性结论和用户业务信息为基础，输出通常是需求规格说明、"
            "逻辑模型以及必要的数据描述。这些结果会直接影响后续总体设计、详细设计、编码和测试。"
            "如果这一阶段理解不准，后面的模块划分、接口设计和验证标准就会失去稳定依据。"
        )
        if artifact_hint:
            p3 += f" 教材中提到的典型分析产物包括：{artifact_hint}。"
        if impact_hint:
            p3 += f" 它之所以重要，还因为教材明确指出它会继续影响：{impact_hint}。"

        p4 = (
            "学习这个知识点时，重点不是背定义，而是把它放回软件定义阶段去理解：先看它在整个阶段中的位置，"
            "再看它要完成的任务、形成的产物，最后再判断它为什么会决定后续设计和实现的方向。"
        )
        return "\n\n".join([p1, p2, p3, p4])

    def _build_general_explanation(self, main_title: str, stage_title: str, basis_text: str) -> str:
        facts = self._sentence_list(basis_text)
        stage_hint = self._pick_fact(facts, [stage_title]) if stage_title else ""
        role_hint = self._pick_fact(facts, [main_title])
        io_hint = self._pick_fact(facts, ["输入", "输出"])
        effect_hint = self._pick_fact(facts, ["设计", "实现", "测试", "维护"])

        p1 = (
            f"{main_title}是{stage_title or '当前学习阶段'}中需要优先掌握的核心知识。理解它时，不能只停留在术语记忆上，"
            "而要把它放回软件工程流程中去看：它负责解决什么问题，和前后阶段如何衔接，以及它为什么会影响后续工作。"
        )
        if stage_hint:
            p1 += f" 教材中与阶段定位最接近的表述是：{stage_hint}。"

        p2 = (
            f"从知识作用上看，{main_title}承担的是把阶段目标进一步落到可执行逻辑上的任务。学习时需要同时关注三个方面："
            "它依赖哪些前置信息、它在当前阶段如何发挥作用、它最终形成什么结果。只有把这三部分连起来，知识点才不会变成零散结论。"
        )
        if role_hint:
            p2 += f" 教材片段中最能说明这一点的内容是：{role_hint}。"
        if io_hint:
            p2 += f" 如果结合输入与输出去看，可以概括为：{io_hint}。"

        p3 = (
            f"{main_title}之所以值得重点掌握，还因为它会继续影响后续设计、实现或验证。"
            "如果只记名称而不理解边界，就很容易在做题或做项目时和相近概念混淆。"
            "更有效的学习方式，是先明确它在阶段中的位置，再结合案例说明它如何推动后续活动。"
        )
        if effect_hint:
            p3 += f" 教材对此的提醒可以概括为：{effect_hint}。"
        return "\n\n".join([p1, p2, p3])

    def _build_core_concepts(self, main_title: str, support_titles: List[str]) -> List[Dict[str, str]]:
        items = [
            {
                "name": main_title,
                "definition": f"{main_title}是当前阶段需要重点理解的核心知识。",
                "why_it_matters": "它会影响阶段任务能否被正确拆解并稳定传递给后续工作。",
                "example": f"结合课程项目，说明 {main_title} 在当前阶段解决什么问题。",
                "common_misunderstanding": "只记住名称，不理解它和前后阶段的关系。",
            }
        ]
        for title in support_titles[:2]:
            items.append(
                {
                    "name": title,
                    "definition": f"{title}是帮助理解 {main_title} 的补充知识点。",
                    "why_it_matters": "它用于区分相近概念，避免把不同阶段任务混在一起。",
                    "example": f"比较 {title} 和 {main_title} 在目标、输入和输出上的差异。",
                    "common_misunderstanding": "把相邻知识点简单看成同义概念。",
                }
            )
        return items[:3]

    def _build_support_items(self, main_title: str, support_titles: List[str]) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for title in support_titles[:2]:
            items.append(
                {
                    "title": title,
                    "explanation": f"{title}可以作为理解“{main_title}”的补充参照。重点不是单独背诵这个概念，而是比较它与主知识点在任务目标、输入信息、输出产物和适用阶段上的不同。",
                    "process": ["先区分概念边界", "再比较任务与产物", "最后梳理阶段衔接"],
                    "input_output": {"input": "教材片段与课程案例", "output": "对补充知识点的准确理解"},
                    "example": f"结合课程项目，说明 {title} 与 {main_title} 分别在什么阶段发挥作用。",
                    "exam_focus": "常考概念边界、作用差异和前后衔接关系。",
                }
            )
        return items

    def _build_mistakes(self, main_title: str) -> List[Dict[str, str]]:
        if self._is_requirement_analysis(main_title):
            return [
                {
                    "mistake": "把需求分析等同于问题定义或可行性研究。",
                    "reason": "三者同处软件定义阶段，但目标不同。前两者负责明确问题与判断可行性，需求分析负责明确系统必须做什么。",
                    "correction": "先分清阶段顺序，再区分每一步各自的任务和产物。",
                    "example": "先判断项目值不值得做，再整理正式需求，而不是一开始就直接写实现细节。",
                },
                {
                    "mistake": "只把需求分析看成写文档。",
                    "reason": "如果忽略沟通、澄清和建模过程，就会把分析活动误解成单纯整理文字。",
                    "correction": "把它理解为“沟通—澄清—建模—确认—固化”的完整过程。",
                    "example": "需求规格说明书只是结果，前面对业务流程和功能边界的确认才是关键。",
                },
                {
                    "mistake": "在需求分析阶段就急于进入详细设计。",
                    "reason": "需求分析关注系统做什么，不负责把实现方案拆到接口和代码层。",
                    "correction": "先稳定需求边界，再进入总体设计和详细设计。",
                    "example": "先确认系统功能，再讨论模块如何划分和接口如何定义。",
                },
            ]
        return [
            {
                "mistake": "只记概念名称，不理解它在流程中的位置。",
                "reason": "这样容易在做题或做项目时与相近知识点混淆。",
                "correction": "把知识点放回阶段流程，明确它之前依赖什么、之后影响什么。",
                "example": f"解释 {main_title} 时，同时说明它之前承接什么，之后支撑什么。",
            },
            {
                "mistake": "会背定义，但说不清输入和输出。",
                "reason": "如果说不清输入输出，就无法真正理解知识点的工程作用。",
                "correction": "从输入、处理过程和输出产物三个角度重新梳理。",
                "example": f"用课程项目说明 {main_title} 形成的结果怎样服务于后续开发。",
            },
        ]

    def _fallback_doc_resource(self, context: Dict[str, Any], knowledge_text: str) -> Dict[str, Any]:
        stage_title = str(context.get("stage_title") or "").strip()
        points = self._context_points(context)
        main_title, basis_text, support_titles = self._extract_primary_basis(knowledge_text)
        if main_title == "课程核心知识":
            main_title = context.get("selected_primary_knowledge_title") or (points[0] if points else stage_title or "课程核心知识")
        topic = stage_title or main_title

        main_explanation = (
            self._build_requirement_explanation(basis_text)
            if self._is_requirement_analysis(main_title)
            else self._build_general_explanation(main_title, stage_title, basis_text)
        )

        content = {
            "resourcetype": "doc",
            "resourcetitle": f"{topic}讲解文档",
            "overview": {
                "title": "本阶段学习导入",
                "content": f"本阶段围绕“{main_title}”展开。学习重点不是孤立背诵概念，而是理解它在软件工程流程中的位置、任务和后续影响。",
            },
            "core_concepts": self._build_core_concepts(main_title, support_titles),
            "main_explanation": {"title": main_title, "content": main_explanation},
            "knowledge_explanation": self._build_support_items(main_title, support_titles),
            "lifecycle_position": {
                "phase": stage_title or "当前学习阶段",
                "before": "前置阶段提供问题背景、目标和约束。",
                "after": "后续阶段会根据本阶段形成的结果继续设计、实现或验证。",
                "connection": f"{main_title}承担承上启下的作用，是阶段衔接中的关键节点。",
            },
            "case_study": {
                "title": "课程项目案例讲解",
                "scenario": "假设团队正在开发一个课程学习系统，需要按软件工程流程逐步推进。",
                "analysis": f"在这个场景中，{main_title}的价值在于帮助团队判断当前阶段到底要完成什么、要交付什么，以及这些结果为何能支撑下一步工作。",
                "takeaway": f"学习 {main_title} 时，要始终追问它解决什么问题、产出什么结果、又如何影响后续环节。",
            },
            "mistakes": self._build_mistakes(main_title),
            "learning_path": [
                "先明确主知识点所在的大阶段以及它前后的关键步骤。",
                "再理解这个知识点要解决的问题、输入信息和输出产物。",
                "最后结合课程案例判断它如何影响后续设计、实现或测试。",
            ],
            "summary": {
                "key_takeaways": [
                    f"{main_title}必须放回软件工程流程中理解。",
                    "学习重点是概念、输入输出和阶段关系的统一。",
                    "如果这一环节理解不准，后续工作很容易偏离目标。",
                ],
                "one_sentence": f"本阶段的核心，是把 {main_title} 从术语记忆转化为流程中的实际判断能力。",
            },
            "self_check": [
                {"question": f"{main_title}主要解决什么问题？", "hint": "从阶段目标和任务角度回答。"},
                {"question": "它依赖什么输入，又会形成什么输出？", "hint": "把输入、处理和产物连起来说。"},
                {"question": "它为什么会影响后续设计或实现？", "hint": "思考后续阶段要以什么为依据。"},
            ],
            "learningresources": [
                {
                    "title": main_title,
                    "source": "课程知识库",
                    "sectionpath": context.get("course_progress") or "",
                    "pages": [],
                    "chunkid": "fallback-doc",
                    "content": basis_text[:260],
                    "images": [],
                }
            ],
        }
        return {
            "resource_type": self.resource_type,
            "title": content["resourcetitle"],
            "content": json.dumps(content, ensure_ascii=False),
            "knowledge_points": [main_title] + [item for item in support_titles if item != main_title],
            "personalization": f"已围绕学生当前最需要补强的“{main_title}”组织讲解，并把内容收束为单主知识点展开。",
            "format": "json",
            "agent_name": self.__class__.__name__,
        }

    @classmethod
    def _contains_forbidden_labels(cls, text: Any) -> bool:
        return bool(FORBIDDEN_LABEL_RE.search(str(text or "")))

    @classmethod
    def _payload_has_forbidden_labels(cls, value: Any) -> bool:
        if isinstance(value, dict):
            return any(cls._payload_has_forbidden_labels(v) for v in value.values())
        if isinstance(value, list):
            return any(cls._payload_has_forbidden_labels(v) for v in value)
        return cls._contains_forbidden_labels(value)

    def _is_doc_content_weak(self, content: Any) -> bool:
        if not isinstance(content, dict):
            return True
        main = content.get("main_explanation") if isinstance(content.get("main_explanation"), dict) else {}
        main_text = str(main.get("content") or main.get("explanation") or "").strip()
        if len(main_text) < 260:
            return True
        if self._payload_has_forbidden_labels(content):
            return True
        if "结合课程知识库内容可知" in main_text or "教材片段" in main_text:
            return True
        if not isinstance(content.get("core_concepts"), list) or not content.get("core_concepts"):
            return True
        return False

    def _invoke_model(self, variables: Dict[str, Any]) -> str:
        if self.chain is None:
            logger.warning(
                "[ResourceAgent] LLM chain unavailable, fallback will be used. resource_type=%s title=%s",
                self.resource_type,
                variables.get("task_plan", "")[:160],
            )
            return ""
        try:
            raw = self.chain.invoke(variables)
        except Exception as exc:
            logger.exception(
                "[ResourceAgent] LLM invocation failed, fallback will be used. resource_type=%s error=%s",
                self.resource_type,
                exc,
            )
            return "调用失败"
        if hasattr(raw, "content"):
            raw = raw.content
        return str(raw or "")

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
        raw = self._invoke_model(variables)

        if self._is_model_error(raw):
            logger.warning(
                "[ResourceAgent] LLM returned unavailable response, fallback will be used. resource_type=%s raw_preview=%s",
                self.resource_type,
                raw[:300],
            )
            return self._fallback_doc_resource(context, knowledge_text) if self.resource_type == "doc" else self._fallback_resource(context, knowledge_text)

        data = parse_json_with_fallback(raw)
        if not isinstance(data, dict):
            logger.warning(
                "[ResourceAgent] LLM response is not valid JSON object, fallback will be used. resource_type=%s raw_preview=%s",
                self.resource_type,
                raw[:300],
            )
            return self._fallback_doc_resource(context, knowledge_text) if self.resource_type == "doc" else self._fallback_resource(context, knowledge_text)

        if self.resource_type == "doc" and data.get("resourcetype"):
            data = {
                "title": data.get("resourcetitle") or data.get("title") or self.default_title,
                "content": data,
                "knowledge_points": data.get("weakpoints") or self._context_points(context),
                "personalization": data.get("personalization") or "已根据学生画像、学习目标和课程知识片段生成结构化讲解文档。",
                "format": data.get("format") or "json",
            }

        if self.resource_type == "doc":
            if self._is_doc_content_weak(data.get("content")):
                logger.warning(
                    "[ResourceAgent] LLM doc content failed quality gate, fallback will be used. title=%s content_type=%s raw_preview=%s",
                    data.get("title") or self.default_title,
                    type(data.get("content")).__name__,
                    raw[:300],
                )
                return self._fallback_doc_resource(context, knowledge_text)

        points = data.get("knowledge_points") or self._context_points(context)
        if not isinstance(points, list):
            points = [str(points)]
        return {
            "resource_type": self.resource_type,
            "title": str(data.get("title") or self.default_title),
            "content": data.get("content"),
            "knowledge_points": [str(item).strip() for item in points if str(item).strip()],
            "personalization": str(data.get("personalization") or f"已结合学生当前知识短板与学习目标生成 {self.resource_type} 资源。"),
            "format": str(data.get("format") or "markdown"),
            "agent_name": self.__class__.__name__,
        }
