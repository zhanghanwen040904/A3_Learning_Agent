"""资源生成服务 — 按资源类型调用 LLM 生成个性化内容"""
import json
import re
import os
from typing import Optional

from ..llm_client import SparkLLM
from ..schemas import ResourceItem, ReviewResult, StudentProfile

# prompt 模板目录
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "agents", "prompts")


def _load_prompt(name: str) -> str:
    path = os.path.join(PROMPT_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _call_llm(prompt: str) -> str:
    llm = SparkLLM()
    return llm.chat(prompt)


def _parse_json(raw: str) -> dict:
    """从 LLM 返回中提取 JSON"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group()) if m else {}


def _build_context(
    knowledge_point: str,
    profile: Optional[StudentProfile],
    chunks: list[dict],
) -> dict:
    """构造填充 prompt 模板的上下文变量"""
    chunks_text = "\n---\n".join(
        f"[{c['id']}] {c['title']}: {c['content']}" for c in chunks
    ) if chunks else "暂无匹配的知识库片段"

    return {
        "knowledge_point": knowledge_point,
        "profile": profile.model_dump_json(indent=2, ensure_ascii=False) if profile else "{}",
        "weak_points": json.dumps(profile.weak_points, ensure_ascii=False) if profile else "[]",
        "retrieved_chunks": chunks_text,
        "message": f"请生成关于「{knowledge_point}」的学习资源",
    }


# ── 各资源类型生成函数 ──

def generate_doc(knowledge_point: str, profile: Optional[StudentProfile],
                 chunks: list[dict]) -> ResourceItem:
    """生成个性化讲解文档 (Markdown)"""
    template = _load_prompt("doc_prompt.txt")
    ctx = _build_context(knowledge_point, profile, chunks)

    prompt = template.format(**{k: ctx.get(k, "") for k in ["profile", "retrieved_chunks", "message"]})
    content = _call_llm(prompt)

    return ResourceItem(
        type="doc",
        title=f"《{knowledge_point}》个性化讲解",
        content=content,
    )


def generate_mindmap(knowledge_point: str, profile: Optional[StudentProfile],
                     chunks: list[dict]) -> ResourceItem:
    """生成思维导图 (Mermaid 格式)"""
    prompt = f"""请为知识点「{knowledge_point}」生成 Mermaid mindmap 格式的思维导图。

参考知识库片段:
{_build_context(knowledge_point, profile, chunks)['retrieved_chunks']}

严格按以下格式输出，不要多余文字:
mindmap
  root(({knowledge_point}))
    子主题1
      细节1
      细节2
    子主题2
      细节1"""

    content = _call_llm(prompt)
    # 如果 LLM 没按格式，做兜底
    if not content.strip().startswith("mindmap"):
        content = f"mindmap\n  root(({knowledge_point}))\n    核心概念\n    关键原理\n    典型应用"

    return ResourceItem(
        type="mindmap",
        title=f"{knowledge_point} 思维导图",
        content=content,
    )


def generate_quiz(knowledge_point: str, profile: Optional[StudentProfile],
                  chunks: list[dict]) -> ResourceItem:
    """生成练习题 (JSON)"""
    template = _load_prompt("quiz_prompt.txt")
    ctx = _build_context(knowledge_point, profile, chunks)

    prompt = template.format(**{k: ctx.get(k, "") for k in ["profile", "knowledge_point", "weak_points"]})
    raw = _call_llm(prompt)
    quiz_data = _parse_json(raw)

    # 兜底
    if not quiz_data.get("question"):
        quiz_data = {
            "type": "choice",
            "question": f"下列关于{knowledge_point}的说法，正确的是？",
            "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
            "answer": 0,
            "explanation": "请参考知识库了解详情。",
            "difficulty": "medium",
            "knowledge_point": knowledge_point,
        }

    return ResourceItem(
        type="quiz",
        title=f"{knowledge_point} 练习题",
        content=json.dumps(quiz_data, ensure_ascii=False),
    )


def generate_code(knowledge_point: str, profile: Optional[StudentProfile],
                  chunks: list[dict]) -> ResourceItem:
    """生成代码案例 (JSON)"""
    template = _load_prompt("code_prompt.txt")
    ctx = _build_context(knowledge_point, profile, chunks)

    prompt = template.format(**{k: ctx.get(k, "") for k in ["profile", "knowledge_point", "retrieved_chunks"]})
    raw = _call_llm(prompt)
    code_data = _parse_json(raw)

    if not code_data.get("source"):
        code_data = {
            "language": "verilog",
            "source": "// 示例代码待生成\nmodule example;\nendmodule",
            "explanation": f"关于{knowledge_point}的代码示例。",
        }

    return ResourceItem(
        type="code",
        title=f"{knowledge_point} 代码案例",
        content=json.dumps(code_data, ensure_ascii=False),
    )


def generate_video_script(knowledge_point: str, profile: Optional[StudentProfile],
                          chunks: list[dict]) -> ResourceItem:
    """生成视频脚本 (Markdown)"""
    prompt = f"""请为知识点「{knowledge_point}」生成一段 1-3 分钟的短视频讲解脚本。

参考知识库:
{_build_context(knowledge_point, profile, chunks)['retrieved_chunks']}

输出 Markdown 格式:
## {knowledge_point} — 短视频讲解脚本
### 第 1 镜 (XX 秒)
- 画面: ...
- 旁白: ...
### 第 2 镜 (XX 秒)
- 画面: ...
- 旁白: ..."""

    content = _call_llm(prompt)

    return ResourceItem(
        type="video_script",
        title=f"{knowledge_point} 视频脚本",
        content=content,
    )


# ── 资源类型 → 生成函数映射 ──

GENERATORS = {
    "doc": generate_doc,
    "mindmap": generate_mindmap,
    "quiz": generate_quiz,
    "code": generate_code,
    "video_script": generate_video_script,
}


def review_resources(resources: list[ResourceItem], chunks: list[dict]) -> ReviewResult:
    """用 Reviewer Agent 审核生成资源"""
    if not resources:
        return ReviewResult(passed=False, notes=["未生成任何资源"])

    template = _load_prompt("reviewer_prompt.txt")
    chunks_text = "\n".join(f"[{c['id']}] {c['title']}: {c['content'][:200]}..." for c in chunks)
    resources_text = "\n---\n".join(
        f"[{r.type}] {r.title}\n{r.content[:500]}" for r in resources
    )

    prompt = template.format(
        generated_resources=resources_text[:3000],
        retrieved_chunks=chunks_text[:2000],
    )

    raw = _call_llm(prompt)
    result = _parse_json(raw)

    passed = result.get("passed", True)
    notes = [
        f"已审核 {len(resources)} 个资源",
        f"引用知识片段: {[c['id'] for c in chunks]}",
    ]
    if result.get("issues"):
        notes.extend(result["issues"])
    if result.get("suggestions"):
        notes.extend(result["suggestions"])

    return ReviewResult(passed=passed, notes=notes)


def generate_resources(
    knowledge_point: str,
    resource_types: list[str],
    profile: Optional[StudentProfile],
    chunks: list[dict],
    skip_review: bool = False,
) -> tuple[list[ResourceItem], ReviewResult]:
    """
    按指定类型生成个性化资源，完成后审核。

    Args:
        knowledge_point: 目标知识点
        resource_types: 资源类型列表
        profile: 学生画像
        chunks: RAG 检索结果
        skip_review: 是否跳过审核（加速调试）

    Returns:
        (resources, review)
    """
    resources: list[ResourceItem] = []

    for rtype in resource_types:
        gen = GENERATORS.get(rtype)
        if gen is None:
            continue
        item = gen(knowledge_point, profile, chunks)
        resources.append(item)

    if skip_review:
        review = ReviewResult(
            passed=True,
            notes=[f"已生成 {len(resources)} 个资源（跳过审核）"],
        )
    else:
        review = review_resources(resources, chunks)

    return resources, review
