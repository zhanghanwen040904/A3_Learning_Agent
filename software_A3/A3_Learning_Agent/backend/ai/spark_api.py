import base64
import hashlib
import hmac
import json
import ssl
import time
from datetime import datetime
from email.utils import formatdate
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode, urlparse

from config import config


def _mock_spark_response(prompt: str) -> str:
    """生成开发模式下的讯飞星火模拟响应。

    功能：在未配置真实讯飞密钥时，根据提示词返回结构化模拟结果，便于联调画像、资源、路径和答疑流程。
    输入：prompt，智能体提示词。
    输出：可被业务模块解析的模拟文本。
    """
    if "学习路径" in prompt or "学习规划师" in prompt:
        return "# 个性化学习路径\n\n## 第1阶段：概念澄清\n- 学习目标：区分监督学习、无监督学习、分类、回归和聚类\n- 推荐资源：课程讲解文档、知识点思维导图\n- 练习方式：完成基础概念判断题\n- 评估指标：能够准确说出有标签数据与无标签数据的区别\n\n## 第2阶段：案例理解\n- 学习目标：通过鸢尾花分类案例理解监督学习完整流程\n- 推荐资源：代码实操案例、分难度练习题\n- 练习方式：运行并修改决策树分类代码\n- 评估指标：能够解释训练集、测试集、准确率的含义\n\n## 第3阶段：拓展应用\n- 学习目标：理解聚类、降维等无监督学习任务的应用边界\n- 推荐资源：拓展阅读材料、智能答疑\n- 练习方式：对比分类任务和聚类任务的输入输出差异\n- 评估指标：能够根据问题场景选择合适的学习方法\n\n## 动态优化建议\n每完成一个阶段后记录错题和疑问，系统将根据练习结果更新画像并调整后续资源推送。"
    if '"doc"' in prompt and '"quiz"' in prompt and '"reading"' in prompt:
        return json.dumps(
            {
                "doc": "# 课程讲解文档\n\n本节围绕监督学习与无监督学习展开。监督学习使用带标签样本训练模型，目标是学习输入到输出的映射；无监督学习处理无标签数据，目标是发现数据内部结构。\n\n## 学习重点\n- 明确标签数据与无标签数据的区别\n- 理解分类、回归、聚类的基本任务\n- 结合教材原文建立概念边界",
                "quiz": "# 分难度练习题\n\n## 基础题\n1. 什么是监督学习？\n2. 聚类属于监督学习还是无监督学习？\n\n## 提升题\n1. 请比较分类与回归任务的输出差异。\n2. 如果一组数据没有标签，应该优先考虑哪类学习方法？",
                "reading": "# 拓展阅读材料\n\n建议阅读机器学习章节中关于分类、回归、聚类的教材内容，并结合鸢尾花分类案例理解监督学习流程。",
            },
            ensure_ascii=False,
        )
    if '"mindmap"' in prompt and '"code"' in prompt:
        return json.dumps(
            {
                "mindmap": "# 机器学习基础思维导图\n- 机器学习\n  - 监督学习\n    - 分类\n    - 回归\n  - 无监督学习\n    - 聚类\n    - 降维\n  - 评价指标\n    - 准确率\n    - 召回率",
                "code": "from sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.tree import DecisionTreeClassifier\nfrom sklearn.metrics import accuracy_score\n\n# 加载鸢尾花数据集，用于演示监督学习中的分类任务\ndata = load_iris()\nX_train, X_test, y_train, y_test = train_test_split(data.data, data.target, test_size=0.2, random_state=42)\n\n# 使用决策树训练分类模型\nmodel = DecisionTreeClassifier(random_state=42)\nmodel.fit(X_train, y_train)\n\n# 预测并计算准确率\npred = model.predict(X_test)\nprint('accuracy:', accuracy_score(y_test, pred))",
            },
            ensure_ascii=False,
        )
    if "knowledge_level" in prompt and "study_style" in prompt and "weak_points" in prompt:
        return json.dumps(
            {
                "knowledge_level": "人工智能导论基础中等，已了解基础概念，但机器学习体系化掌握不足",
                "study_style": "偏好案例驱动、图解说明与代码实操结合的学习方式",
                "weak_points": "监督学习、无监督学习、模型评估指标、算法应用边界",
                "study_goal": "两周内掌握机器学习核心概念，并能完成基础代码实验",
                "study_time_prefer": "晚上学习效率较高，适合安排60分钟以内的阶段任务",
                "course_progress": "已完成人工智能概论，正在进入机器学习基础章节",
            },
            ensure_ascii=False,
        )
    return "# 智能答疑\n\n根据课程知识库，监督学习依赖带标签数据学习输入到输出的映射，常见任务包括分类和回归；无监督学习用于无标签数据，常见任务包括聚类和降维。\n\n## 图解说明\n- 有标签数据 → 监督学习 → 分类/回归\n- 无标签数据 → 无监督学习 → 聚类/降维\n\n## 自测\n请判断：房价预测属于分类还是回归？"


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


def _create_spark_auth_url() -> str:
    """生成讯飞星火 WebSocket 鉴权地址。

    功能：按照讯飞星火接口规范签名，生成带鉴权参数的访问 URL。
    输入：config 中的 app_id、api_key、api_secret、spark_url。
    输出：可直接连接的 WebSocket URL。
    """
    parsed = urlparse(config.XFYUN_SPARK_URL)
    host = parsed.netloc
    path = parsed.path
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(
        config.XFYUN_API_SECRET.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{config.XFYUN_API_KEY}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": host})
    return f"{config.XFYUN_SPARK_URL}?{query}"


def spark_chat(prompt: str) -> str:
    """同步调用讯飞星火 V3.5 生成文本。

    功能：向讯飞星火 V3.5 发送单轮提示词并返回文本结果。
    输入：prompt，自然语言提示词。
    输出：成功时返回模型文本；失败时返回 JSON 字符串格式的标准错误信息。
    """
    if not prompt or not prompt.strip():
        return json.dumps(_standard_error("prompt不能为空"), ensure_ascii=False)
    if config.MOCK_AI:
        return _mock_spark_response(prompt)
    if not all([config.XFYUN_APP_ID, config.XFYUN_API_KEY, config.XFYUN_API_SECRET]):
        return json.dumps(_standard_error("讯飞星火密钥未配置"), ensure_ascii=False)

    def _call() -> str:
        import websocket

        answer_parts = []
        error_holder = {"error": None}

        def on_message(ws, message):
            data = json.loads(message)
            header = data.get("header", {})
            code = header.get("code", 0)
            if code != 0:
                error_holder["error"] = data
                ws.close()
                return
            choices = data.get("payload", {}).get("choices", {})
            for item in choices.get("text", []):
                answer_parts.append(item.get("content", ""))
            if choices.get("status") == 2:
                ws.close()

        def on_error(ws, error):
            error_holder["error"] = str(error)

        def on_open(ws):
            payload = {
                "header": {"app_id": config.XFYUN_APP_ID, "uid": "a3_learning_agent"},
                "parameter": {
                    "chat": {
                        "domain": config.XFYUN_SPARK_DOMAIN,
                        "temperature": 0.5,
                        "max_tokens": 4096,
                    }
                },
                "payload": {"message": {"text": [{"role": "user", "content": prompt}]}}
            }
            ws.send(json.dumps(payload, ensure_ascii=False))

        ws = websocket.WebSocketApp(
            _create_spark_auth_url(),
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
        )
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_timeout=config.AI_TIMEOUT)
        if error_holder["error"]:
            raise RuntimeError(error_holder["error"])
        return "".join(answer_parts).strip()

    try:
        return _retry_call(_call)
    except Exception as exc:
        return json.dumps(_standard_error("讯飞星火调用失败", str(exc)), ensure_ascii=False)


def see_dance_generate(text: str) -> str:
    """同步调用讯飞 SeeDance 生成教学短视频。

    功能：根据知识点文本生成 40-90 秒教学短视频，默认提示词约束为 60 秒以内。
    输入：text，教学视频脚本或核心知识点文本。
    输出：成功时返回视频 URL；失败时返回 JSON 字符串格式的标准错误信息。
    """
    if not text or not text.strip():
        return json.dumps(_standard_error("text不能为空"), ensure_ascii=False)
    if config.MOCK_AI:
        return "https://example.com/mock-ai-intro-teaching-video.mp4"
    if not config.SEEDANCE_API_URL or not config.SEEDANCE_API_KEY:
        return json.dumps(_standard_error("讯飞SeeDance配置未完成"), ensure_ascii=False)

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
            return json.dumps(_standard_error("讯飞SeeDance未返回视频URL"), ensure_ascii=False)
        return video_url
    except Exception as exc:
        return json.dumps(_standard_error("讯飞SeeDance调用失败", str(exc)), ensure_ascii=False)


def _local_content_audit(text: str) -> bool:
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


def content_audit(text: str) -> bool:
    """同步调用讯飞内容审核接口。

    功能：审核输入文本是否安全合规；未配置真实审核接口时使用本地基础审核兜底，避免正常课程文本被误拦截。
    输入：text，需要审核的文本。
    输出：通过返回 True；明确违规或真实审核不通过返回 False。
    """
    if not text or not text.strip():
        return False
    if config.MOCK_AI:
        return _local_content_audit(text)
    if not config.CONTENT_AUDIT_API_URL or not config.CONTENT_AUDIT_API_KEY:
        return _local_content_audit(text)

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
        return _local_content_audit(text)
