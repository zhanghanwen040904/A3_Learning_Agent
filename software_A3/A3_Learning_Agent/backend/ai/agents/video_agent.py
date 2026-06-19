import json
from typing import Any, Dict

from ai.json_utils import extract_json_object
from ai.spark_api import see_dance_generate, spark_chat
from .base_agent import XunfeiAgentSpec


class VideoAgent:
    """视频生成智能体。

    功能：基于核心知识点调用讯飞 SeeDance 生成 60 秒以内教学短视频。
    输入：知识点文本。
    输出：教学短视频 URL 或标准错误 JSON 字符串。
    """

    def __init__(self):
        self.role = "多模态视频制作师"
        self.goal = "基于单个核心知识点生成聚焦、简短、适合本科生学习的教学短视频。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["see_dance_generate"],
            input_schema="核心知识点文本",
            output_schema="教学短视频URL",
        )

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        prompt = f"""
[RESOURCE:VIDEO]
你是多模态视频制作师。请为学生设计60秒以内教学短视频。
学生上下文：{json.dumps(context, ensure_ascii=False)}
任务计划：{json.dumps(task_plan, ensure_ascii=False)}
教材依据：{knowledge_text[:2400]}
返工意见：{feedback or '无'}
严格返回JSON：
{{"title":"","script":"完整旁白","storyboard":[{{"time":"0-10s","visual":"画面","narration":"旁白","subtitle":"字幕"}}],"knowledge_points":[],"personalization":""}}
分镜至少4段，必须同时包含画面、旁白和字幕，并体现学生专业、短板与学习偏好。
""".strip()
        data = extract_json_object(spark_chat(prompt))
        script = str(data.get("script") or "视频脚本生成失败")
        storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), list) else []
        lines = ["## 教学视频脚本", script, "", "## 分镜表"]
        for item in storyboard:
            lines.append(
                f"- **{item.get('time', '片段')}**｜画面：{item.get('visual', '')}｜旁白：{item.get('narration', '')}｜字幕：{item.get('subtitle', '')}"
            )
        video_url = see_dance_generate(script) if script and script != "视频脚本生成失败" else ""
        if video_url:
            lines.extend(["", "## 视频生成结果", video_url])
        return {
            "resource_type": "video",
            "title": str(data.get("title") or "个性化AI教学短视频"),
            "content": "\n".join(lines),
            "video_url": video_url,
            "storyboard": storyboard,
            "knowledge_points": data.get("knowledge_points") or [str(context.get("weak_points") or "课程核心知识")],
            "personalization": str(data.get("personalization") or f"围绕学生薄弱点“{context.get('weak_points', '')}”设计短时长分镜。"),
            "format": "video_storyboard",
            "agent_name": self.__class__.__name__,
        }
