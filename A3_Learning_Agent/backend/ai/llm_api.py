import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from config import config


def _mock_llm_response(prompt: str) -> str:
    """生成开发模式下的模型模拟响应。

    功能：在未配置真实模型密钥时，根据提示词返回结构化模拟结果，便于联调画像、资源、路径和答疑流程。
    输入：prompt，智能体提示词。
    输出：可被业务模块解析的模拟文本。
    """
    topic = "需求分析与软件设计"
    for candidate in ["需求分析", "可行性研究", "总体设计", "详细设计", "编码", "软件测试", "调试", "软件维护", "项目管理", "质量保证", "敏捷开发", "DevOps"]:
        if candidate in prompt:
            topic = candidate
            break
    major = "软件工程" if "软件工程" in prompt else "计算机相关专业"
    personalization = f"针对{major}学生在“{topic}”方面的薄弱点，并结合其案例、图解和代码偏好进行设计。"

    if "[RESOURCE:DOC]" in prompt:
        content = f"""# {topic}个性化课程讲解

## 学习目标
理解{topic}的核心概念、基本过程与适用边界，能够结合{major}场景解释其作用。

## 前置知识
建议先掌握函数、基本概率概念和Python基础。遇到公式时先关注输入、处理过程和输出，再理解符号细节。

## 核心讲解
{topic}不是孤立术语，而是人工智能系统完成学习或推理的重要环节。学习时可以把它拆成“数据或状态从哪里来、系统进行什么计算、结果怎样被评价、下一步如何调整”四个问题。课程教材中的定义用于划定概念边界，案例用于建立直觉，代码实验则用于验证过程。

## 专业案例
在{major}项目中，可以把一次模型训练看成可测试的软件流水线：输入数据经过处理与计算得到输出，再利用评价结果定位问题并调整参数。这种视角能把抽象算法和工程中的日志、测试、迭代联系起来。

## 易错点
1. 只记结论而忽略输入输出条件；2. 把训练过程和推理过程混为一谈；3. 只看最终指标而不检查数据和中间步骤。

## 三问自测
1. 请用一句话说明{topic}解决什么问题。2. 它的输入和输出分别是什么？3. 如果结果不理想，应优先检查哪些环节？

## 总结
先建立流程直觉，再结合教材定义、图解和代码逐层验证，是掌握{topic}更稳妥的路径。"""
        return json.dumps({"title": f"{topic}递进式课程讲解", "content": content, "knowledge_points": [topic], "personalization": personalization, "format": "markdown"}, ensure_ascii=False)
    if "[RESOURCE:QUIZ]" in prompt:
        content = f"""# {topic}分层多题型练习

## 基础层
1. **判断题｜基础｜知识点：{topic}**：学习过程只需要关注最终结果，不必理解中间计算。（错误）\n解析：中间过程决定结果是否可信，也是定位错误的关键。
2. **选择题｜基础｜知识点：概念边界**：学习{topic}时最合理的第一步是？A.死记公式 B.明确输入输出 C.忽略条件 D.只看代码。\n答案：B。解析：输入、处理、输出构成理解算法的主线。

## 提升层
3. **简答题｜提升｜知识点：流程理解**：请用“输入—计算—评价—调整”描述{topic}。\n参考答案：应分别说明信息来源、核心计算、评价依据以及根据评价进行的更新，并指出各环节之间的依赖关系。
4. **纠错题｜提升｜知识点：常见误区**：某同学认为训练指标越高，模型在任何场景都越可靠。指出错误。\n解析：还需考虑数据划分、过拟合、场景变化和指标选择。

## 应用层
5. **工程应用题｜应用｜知识点：实验设计**：为一个{major}课程项目设计验证{topic}的最小实验。\n参考答案：固定数据与随机种子，记录输入、中间结果和评价指标，只改变一个关键参数，对比结果并解释变化原因。"""
        return json.dumps({"title": f"{topic}三级诊断练习", "content": content, "knowledge_points": [topic, "概念边界", "实验设计"], "personalization": personalization, "format": "markdown"}, ensure_ascii=False)
    if "[RESOURCE:READING]" in prompt:
        content = f"""# 从课程概念到前沿应用：{topic}

## 为什么推荐
这份导读针对学生当前对{topic}理解不稳的问题，先巩固课程定义，再连接{major}中的工程实践，避免直接阅读前沿材料时被术语淹没。

## 阅读路线
第一部分回到课程教材，标出定义、输入输出和基本步骤；第二部分寻找一个小型案例，观察每一步的数据变化；第三部分阅读工程实践中的模型调试、可解释性或可靠性材料，比较理论假设与真实系统约束。

## 前沿连接
当前人工智能工程越来越重视可靠性、可解释性、数据质量和资源效率。理解{topic}时，不仅要问“效果是否更好”，还要问“为什么有效、在什么条件下失效、怎样复现实验”。

## 阅读问题
1. 教材定义包含哪些必要条件？2. 工程案例中哪些因素不在简化公式里？3. 如果数据或场景发生变化，结论是否仍成立？

## 进一步探索
建议从课程知识库的对应章节开始，再检索高校课程公开讲义或权威框架文档。对无法核验的文章和链接只作为线索，不作为事实依据。"""
        return json.dumps({"title": f"{topic}课程到前沿导读", "content": content, "knowledge_points": [topic, "可靠性", "工程实践"], "personalization": personalization, "format": "markdown"}, ensure_ascii=False)
    if "[RESOURCE:MINDMAP]" in prompt:
        content = f"""mindmap
  root(({topic}))
    概念
      解决的问题
      输入与输出
      适用条件
    原理
      信息流动
      核心计算
      评价依据
    步骤
      准备数据
      执行计算
      评价结果
      调整优化
    {major}案例
      最小可运行实验
      日志与测试
      结果解释
    易错点
      混淆训练与推理
      忽略数据条件
      只看单一指标"""
        return json.dumps({"title": f"{topic}知识结构图", "content": content, "knowledge_points": [topic], "personalization": personalization, "format": "mermaid"}, ensure_ascii=False)
    if "[RESOURCE:CODE]" in prompt:
        content = f'''# {topic}最小可验证实验

## 学习目标
通过可重复的数值实验观察参数更新和误差变化，把抽象过程转化为可检查的工程步骤。

## 环境与依赖
Python 3.10+，仅依赖 numpy。运行：`pip install numpy`。

```python
import numpy as np

np.random.seed(42)
x = np.array([1.0, 2.0, 3.0, 4.0])
y = 2.0 * x + 1.0
w, b, learning_rate = 0.0, 0.0, 0.01

for epoch in range(201):
    prediction = w * x + b
    error = prediction - y
    loss = np.mean(error ** 2)
    grad_w = 2 * np.mean(error * x)
    grad_b = 2 * np.mean(error)
    w -= learning_rate * grad_w
    b -= learning_rate * grad_b
    if epoch % 50 == 0:
        print(epoch, round(float(loss), 6), round(float(w), 4), round(float(b), 4))
```

## 预期结果
损失逐步下降，参数接近 w=2、b=1。固定随机种子便于复现实验。

## 修改任务
分别把学习率改为0.001和0.1，记录收敛速度；增加噪声后观察结果；为每轮训练增加断言或日志。

## 常见错误
学习率过大会震荡，数组形状不一致会造成错误广播，只看最终损失会遗漏训练过程异常。'''
        return json.dumps({"title": f"{topic}Python实操", "content": content, "knowledge_points": [topic, "参数更新", "损失函数"], "personalization": personalization, "format": "markdown_code"}, ensure_ascii=False)
    if "[RESOURCE:VIDEO]" in prompt:
        script = f"今天用一分钟理解{topic}。先看输入和目标，再观察系统如何计算、评价并调整。把它想成一次有日志、有测试的{major}流水线：每一步都能检查，每次修改都有依据。最后请暂停视频，用一句话复述输入、处理和输出。"
        storyboard = [
            {"time": "0-10s", "visual": f"标题与{topic}流程总览", "narration": f"一分钟理解{topic}", "subtitle": "先看完整流程"},
            {"time": "10-25s", "visual": "输入、计算、输出依次点亮", "narration": "从输入出发，跟踪核心计算直到得到输出", "subtitle": "输入 → 计算 → 输出"},
            {"time": "25-42s", "visual": f"{major}项目中的日志和测试面板", "narration": "用评价指标检查结果，并根据误差调整", "subtitle": "评价 → 调整"},
            {"time": "42-60s", "visual": "自测卡片与思维导图", "narration": "请复述流程，并指出一个最容易出错的环节", "subtitle": "暂停并完成自测"},
        ]
        return json.dumps({"title": f"一分钟理解{topic}", "script": script, "storyboard": storyboard, "knowledge_points": [topic], "personalization": personalization}, ensure_ascii=False)

    if "学习路径" in prompt or "学习规划师" in prompt:
        return "# 个性化学习路径\n\n## 第1阶段：概念澄清\n- 学习目标：理解软件生命周期、需求分析、总体设计和详细设计之间的关系\n- 推荐资源：课程讲解文档、知识点思维导图\n- 练习方式：完成基础概念判断题和流程排序题\n- 评估指标：能够准确说明每个阶段的输入、输出和核心产物\n\n## 第2阶段：案例理解\n- 学习目标：以在线学习平台为例完成需求到设计的转化\n- 推荐资源：代码实操案例、分层练习题、拓展阅读\n- 练习方式：编写用例描述、模块划分和接口草案\n- 评估指标：能够把用户需求转化为功能模块和数据流\n\n## 第3阶段：工程实践\n- 学习目标：理解编码、测试、调试和维护如何支撑软件质量\n- 推荐资源：测试案例、代码实操、智能答疑\n- 练习方式：为一个功能设计单元测试与异常场景测试\n- 评估指标：能够设计覆盖正常流程、边界条件和异常输入的测试用例\n\n## 动态优化建议\n每完成一个阶段后记录错题和疑问，系统将根据练习结果更新画像并调整后续资源推送。"
    if '"doc"' in prompt and '"quiz"' in prompt and '"reading"' in prompt:
        return json.dumps(
            {
                "doc": "# 课程讲解文档\n\n本节围绕软件工程中的需求分析与软件设计展开。需求分析用于明确用户目标、业务规则和系统边界；总体设计将需求转化为系统架构、模块划分和数据流；详细设计进一步明确模块内部逻辑、接口和关键算法。\n\n## 学习重点\n- 明确需求规格说明书、总体设计说明书和详细设计说明书的区别\n- 理解从用户需求到模块设计的逐层细化过程\n- 结合教材原文建立概念边界",
                "quiz": "# 分难度练习题\n\n## 基础题\n1. 需求分析阶段的主要输出是什么？\n2. 总体设计和详细设计有什么区别？\n\n## 提升题\n1. 请为在线学习系统写出三个核心用例。\n2. 如果需求经常变化，设计阶段应该如何降低返工风险？",
                "reading": "# 拓展阅读材料\n\n建议阅读软件工程教材中关于需求分析、总体设计、详细设计、编码测试和维护的章节，并结合一个课程管理系统案例理解从需求到实现的完整工程流程。",
            },
            ensure_ascii=False,
        )
    if '"mindmap"' in prompt and '"code"' in prompt:
        return json.dumps(
            {
                "mindmap": "# 软件工程基础思维导图\n- 软件工程\n  - 需求分析\n    - 用户目标\n    - 业务规则\n    - 系统边界\n  - 总体设计\n    - 架构设计\n    - 模块划分\n  - 详细设计\n    - 接口设计\n    - 算法逻辑\n  - 测试与维护\n    - 测试用例\n    - 缺陷修复",
                "code": "def validate_requirement(requirement):\n    required_fields = ['actor', 'goal', 'input', 'output']\n    missing = [field for field in required_fields if not requirement.get(field)]\n    return {\n        'valid': not missing,\n        'missing_fields': missing,\n        'suggestion': '补全参与者、目标、输入和输出后再进入设计阶段' if missing else '可以进入模块设计'\n    }\n\ncase = {\n    'actor': '学生',\n    'goal': '提交在线作业',\n    'input': '作业文件',\n    'output': '提交结果和时间戳'\n}\nprint(validate_requirement(case))",
            },
            ensure_ascii=False,
        )
    if all(key in prompt for key in ["major", "target_course", "knowledge_level", "study_style", "weak_points", "preferred_resource"]):
        return json.dumps(
            {
                "major": major,
                "target_course": "软件工程",
                "knowledge_level": "软件工程基础中等，已了解软件生命周期概念，但需求分析、设计和测试之间的衔接还不够稳",
                "study_style": "偏好案例驱动、图解说明与代码实操结合的学习方式",
                "weak_points": topic,
                "study_goal": f"在计划周期内掌握 {topic}，并能完成基础工程案例分析",
                "study_time_prefer": "晚上学习效率较高，适合安排 60 分钟以内的阶段任务",
                "course_progress": "已完成软件工程概述，正在进入需求分析和软件设计章节",
                "challenge_scene": f"看到 {topic} 的流程图、文档模板和工程案例时容易对不上号",
                "preferred_resource": "更喜欢图解、分层练习、案例拆解和短视频讲解",
                "profile_summary": f"{major}学生，在 {topic} 方面需要通过图解与案例结合的方式巩固理解",
            },
            ensure_ascii=False,
        )
    if "knowledge_level" in prompt and "study_style" in prompt and "weak_points" in prompt:
        return json.dumps(
            {
                "knowledge_level": "软件工程基础中等，已了解软件生命周期概念，但需求分析、设计和测试之间的衔接还不够稳",
                "study_style": "偏好案例驱动、图解说明与代码实操结合的学习方式",
                "weak_points": topic,
                "study_goal": f"在计划周期内掌握{topic}，并能完成基础工程案例分析",
                "study_time_prefer": "晚上学习效率较高，适合安排60分钟以内的阶段任务",
                "course_progress": "已完成软件工程概述，正在进入需求分析和软件设计章节",
            },
            ensure_ascii=False,
        )
    return "# 智能答疑\n\n根据软件工程课程知识库，需求分析负责明确用户目标、业务规则和系统边界；总体设计负责确定系统架构和模块划分；详细设计则进一步描述模块内部逻辑、接口和关键算法。\n\n## 图解说明\n- 用户问题 → 需求分析 → 需求规格说明书\n- 需求规格 → 总体设计 → 架构与模块\n- 模块职责 → 详细设计 → 接口、流程与伪代码\n\n## 自测\n请判断：为在线学习系统划分“用户管理、课程资源、作业提交”模块，主要属于需求分析还是总体设计？"


def _standard_error(message: str, detail: Optional[Any] = None) -> Dict[str, Any]:
    """生成标准错误信息。

    功能：统一封装外部 AI 接口异常。
    输入：错误说明和可选错误详情。
    输出：包含 success=false 的字典。
    """
    return {"success": False, "error": message, "detail": detail}


def _retry_call(func: Callable[[], Any], retry_times: Optional[int] = None) -> Any:
    """执行带重试的同步调用。

    功能：对不稳定的网络接口进行简单重试。
    输入：无参函数和重试次数。
    输出：函数成功执行后的返回值；多次失败后抛出最后一次异常。
    """
    last_error = None
    total = retry_times or config.AI_RETRY_TIMES
    for index in range(total):
        try:
            return func()
        except Exception as exc:
            last_error = exc
            if index < total - 1:
                time.sleep(config.AI_RETRY_INTERVAL * (index + 1))
    raise last_error


def _extract_http_error(response) -> str:
    text = ""
    try:
        text = response.text
    except Exception:
        pass
    if len(text) > 1200:
        text = text[:1200] + "...(已截断)"
    return f"HTTP {response.status_code}: {text or response.reason}"


def _limit_model_prompt(prompt: str) -> str:
    max_chars = int(__import__("os").getenv("BAILIAN_MAX_INPUT_CHARS", "2500"))
    text = str(prompt or "")
    if len(text) <= max_chars:
        return text
    head_len = int(max_chars * 0.68)
    tail_len = max_chars - head_len
    return text[:head_len].rstrip() + "\n\n...(因模型上下文限制，中间内容已截断)...\n\n" + text[-tail_len:].lstrip()


def _call_bailian_compatible(prompt: str) -> str:
    import requests

    payload = {
        "model": config.BAILIAN_MODEL or "qwen-plus",
        "messages": [{"role": "user", "content": _limit_model_prompt(prompt)}],
        "temperature": 0.5,
        "max_tokens": int(__import__("os").getenv("BAILIAN_MAX_TOKENS", "1024")),
        "stream": False,
    }
    response = requests.post(
        config.BAILIAN_BASE_URL,
        headers={
            "Authorization": f"Bearer {config.BAILIAN_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.AI_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(_extract_http_error(response))
    data = response.json()
    text = _extract_chat_text(data)
    if text:
        return text
    raise RuntimeError(f"Bailian接口未返回有效内容：{data}")


def _call_spark_compatible(prompt: str) -> str:
    import requests

    payload = {
        "model": config.SPARK_MODEL or "4.0Ultra",
        "messages": [{"role": "user", "content": _limit_model_prompt(prompt)}],
        "temperature": 0.5,
        "max_tokens": int(__import__("os").getenv("AI_MAX_TOKENS", "1024")),
        "stream": False,
    }
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        config.SPARK_BASE_URL,
        headers={
            "Authorization": f"Bearer {config.SPARK_APIPASSWORD}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.AI_TIMEOUT,
    )
    if response.status_code >= 400:
        raise RuntimeError(_extract_http_error(response))
    data = response.json()
    text = _extract_chat_text(data)
    if text:
        return text
    raise RuntimeError(f"讯飞星火接口未返回有效内容：{data}")


def _anthropic_candidate_urls() -> List[str]:
    base_url = str(config.ANTHROPIC_BASE_URL or "").rstrip("/")
    if not base_url:
        return []
    candidates = []
    if base_url.endswith("/messages") or base_url.endswith("/chat/completions"):
        candidates.append(base_url)
    elif base_url.endswith("/v1"):
        candidates.extend([f"{base_url}/messages", f"{base_url}/chat/completions"])
    else:
        candidates.extend([f"{base_url}/v1/messages", f"{base_url}/messages", f"{base_url}/v1/chat/completions"])
    result = []
    for url in candidates:
        if url not in result:
            result.append(url)
    return result


def _anthropic_header_variants() -> List[Dict[str, str]]:
    token = config.ANTHROPIC_AUTH_TOKEN
    return [
        {
            "x-api-key": token,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        {
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    ]


def _extract_chat_text(data: dict) -> str:
    content = data.get("content")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif item.get("content"):
                    parts.append(str(item["content"]))
        text = "".join(parts).strip()
        if text:
            return text
    if isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0]
        message = choice.get("message") or {}
        content = message.get("content") or choice.get("text") or ""
        if content:
            return str(content).strip()
    if data.get("completion"):
        return str(data["completion"]).strip()
    if data.get("answer") or data.get("content"):
        return str(data.get("answer") or data.get("content")).strip()
    if isinstance(data.get("data"), dict):
        nested = data["data"]
        if nested.get("answer") or nested.get("content"):
            return str(nested.get("answer") or nested.get("content")).strip()
    return ""


def _call_anthropic_compatible(prompt: str) -> str:
    import requests

    model = config.ANTHROPIC_MODEL or config.ANTHROPIC_SMALL_FAST_MODEL
    anthropic_payload = {
        "model": model,
        "max_tokens": int(__import__("os").getenv("BAILIAN_MAX_TOKENS", "1024")),
        "temperature": 0.5,
        "messages": [{"role": "user", "content": _limit_model_prompt(prompt)}],
    }
    openai_payload = {
        "model": model,
        "temperature": 0.5,
        "max_tokens": int(__import__("os").getenv("BAILIAN_MAX_TOKENS", "1024")),
        "messages": [{"role": "user", "content": _limit_model_prompt(prompt)}],
    }
    errors = []
    for url in _anthropic_candidate_urls():
        payload = openai_payload if url.endswith("/chat/completions") else anthropic_payload
        for headers in _anthropic_header_variants():
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=config.AI_TIMEOUT)
                if response.status_code >= 400:
                    errors.append(f"{url} -> {_extract_http_error(response)}")
                    continue
                data = response.json()
                text = _extract_chat_text(data)
                if text:
                    return text
                errors.append(f"{url} -> 未返回有效内容：{data}")
            except Exception as exc:
                errors.append(f"{url} -> {exc}")
    raise RuntimeError("; ".join(errors[-6:]) or "settings.json大模型接口不可用")


def _has_anthropic_compatible_config() -> bool:
    return bool(config.ANTHROPIC_AUTH_TOKEN and config.ANTHROPIC_BASE_URL and (config.ANTHROPIC_MODEL or config.ANTHROPIC_SMALL_FAST_MODEL))


def llm_chat(prompt: str) -> str:
    """同步调用当前配置的大模型生成文本。

    功能：根据 AI_PROVIDER 选择当前启用的大模型，支持讯飞星火、百炼及 Anthropic/OpenAI 兼容接口。
    输入：prompt，自然语言提示词。
    输出：成功时返回模型文本；失败时返回 JSON 字符串格式的标准错误信息。
    """
    if not prompt or not prompt.strip():
        return json.dumps(_standard_error("prompt不能为空"), ensure_ascii=False)
    if config.MOCK_AI:
        return _mock_llm_response(prompt)

    use_spark = config.AI_PROVIDER in {"spark", "xfyun", "iflytek"}
    if use_spark:
        if not (config.SPARK_APIPASSWORD and config.SPARK_BASE_URL and config.SPARK_MODEL):
            return json.dumps(_standard_error("讯飞星火配置不完整"), ensure_ascii=False)
        try:
            return _retry_call(lambda: _call_spark_compatible(prompt))
        except Exception as exc:
            return json.dumps(_standard_error("讯飞星火调用失败", str(exc)), ensure_ascii=False)

    use_bailian = config.AI_PROVIDER in {"bailian", "dashscope", "qwen"}
    if use_bailian:
        if not (config.BAILIAN_API_KEY and config.BAILIAN_BASE_URL and config.BAILIAN_MODEL):
            return json.dumps(_standard_error("阿里云百炼配置不完整"), ensure_ascii=False)
        try:
            return _retry_call(lambda: _call_bailian_compatible(prompt))
        except Exception as exc:
            return json.dumps(_standard_error("阿里云百炼调用失败", str(exc)), ensure_ascii=False)

    use_anthropic = config.AI_PROVIDER in {"anthropic", "settings", "claude"}
    if use_anthropic:
        if not _has_anthropic_compatible_config():
            return json.dumps(_standard_error("settings.json大模型配置不完整"), ensure_ascii=False)
        try:
            return _retry_call(lambda: _call_anthropic_compatible(prompt))
        except Exception as exc:
            return json.dumps(_standard_error("settings.json大模型调用失败", str(exc)), ensure_ascii=False)
    return json.dumps(
        _standard_error(f"不支持的 AI_PROVIDER：{config.AI_PROVIDER}，当前请使用 spark、bailian 或 settings"),
        ensure_ascii=False,
    )


def generate_teaching_video(text: str) -> str:
    """同步调用视频服务生成教学短视频。

    功能：根据知识点文本生成 40-90 秒教学短视频，默认提示词约束为 60 秒以内。
    输入：text，教学视频脚本或核心知识点文本。
    输出：成功时返回视频 URL；失败时返回 JSON 字符串格式的标准错误信息。
    """
    if not text or not text.strip():
        return json.dumps(_standard_error("text不能为空"), ensure_ascii=False)
    if config.MOCK_AI:
        return "https://example.com/mock-ai-intro-teaching-video.mp4"
    if not config.SEEDANCE_API_URL or not config.SEEDANCE_API_KEY:
        return json.dumps(_standard_error("视频生成服务配置未完成"), ensure_ascii=False)

    def _call() -> str:
        import requests

        payload = {
            "text": text,
            "duration": 60,
            "style": "educational",
            "resolution": "720p",
            "created_at": datetime.utcnow().isoformat(),
        }
        response = requests.post(
            config.SEEDANCE_API_URL,
            headers={"Authorization": f"Bearer {config.SEEDANCE_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=config.AI_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("video_url") or data.get("url") or data.get("data", {}).get("video_url", "")

    try:
        video_url = _retry_call(_call)
        if not video_url:
            return json.dumps(_standard_error("视频生成服务未返回视频 URL"), ensure_ascii=False)
        return video_url
    except Exception as exc:
        return json.dumps(_standard_error("视频生成服务调用失败", str(exc)), ensure_ascii=False)


def _local_audit_content(text: str) -> bool:
    blocked_terms = [
        "违法犯罪",
        "暴力恐怖",
        "色情",
        "赌博",
        "毒品",
        "诈骗",
        "自杀",
        "仇恨",
    ]
    lowered = str(text).lower()
    return bool(text and text.strip()) and not any(term in lowered for term in blocked_terms)


def audit_content(text: str) -> bool:
    """同步调用内容审核接口。

    功能：审核输入文本是否安全合规；未配置真实审核接口时使用本地基础审核兜底，避免正常课程文本被误拦截。
    输入：text，需要审核的文本。
    输出：通过返回 True；明确违规或真实审核不通过返回 False。
    """
    if not text or not text.strip():
        return False
    if config.MOCK_AI:
        return _local_audit_content(text)
    if not config.CONTENT_AUDIT_API_URL or not config.CONTENT_AUDIT_API_KEY:
        return _local_audit_content(text)

    def _call() -> bool:
        import requests

        response = requests.post(
            config.CONTENT_AUDIT_API_URL,
            headers={"Authorization": f"Bearer {config.CONTENT_AUDIT_API_KEY}", "Content-Type": "application/json"},
            json={"content": text},
            timeout=config.AI_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        if "passed" in data:
            return bool(data["passed"])
        if "suggestion" in data:
            return str(data["suggestion"]).lower() in {"pass", "normal", "allow"}
        if "code" in data and "risk" in data:
            return int(data.get("code", -1)) == 0 and not data.get("risk")
        return False

    try:
        return bool(_retry_call(_call))
    except Exception:
        return _local_audit_content(text)

