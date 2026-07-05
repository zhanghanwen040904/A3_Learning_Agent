import json
from typing import Any, Dict

from ai.json_utils import extract_json_object
from ai.spark_api import see_dance_generate, spark_chat
from .base_agent import XunfeiAgentSpec


class VideoAgent:
    def __init__(self):
        self.role = "软件工程短视频脚本设计师"
        self.goal = "基于本地知识库生成 60 秒以内教学短视频脚本，并在服务可用时生成视频。"
        self.agent = XunfeiAgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["spark_chat", "see_dance_generate"],
            input_schema="学生画像 + 本地知识库上下文 + 资源规划",
            output_schema='{"title":"","script":"","storyboard":[],"knowledge_points":[],"personalization":""}',
        )

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        prompt = f"""
你是软件工程课程短视频脚本设计师。请严格依据【本地知识库上下文】生成 60 秒以内教学短视频脚本。

必须返回 JSON，不要 Markdown 代码块：
{{
  "title": "视频标题",
  "script": "完整旁白脚本",
  "storyboard": [
    {{"time":"0-10s","visual":"画面建议","narration":"旁白","subtitle":"字幕"}}
  ],
  "knowledge_points": ["知识点1"],
  "personalization": "如何适配学生画像"
}}

要求：
1. 分镜 4-6 段，每段包含画面、旁白、字幕。
2. 如果知识库有图片，画面建议中写“使用图片：图片说明（图片路径）”。
3. 不要编造图片、页码和知识点。
4. 内容必须是软件工程，不要输出人工智能导论或机器学习案例。

学生画像：
{json.dumps(context, ensure_ascii=False, indent=2)}

任务规划：
{json.dumps(task_plan, ensure_ascii=False, indent=2)}

本地知识库上下文：
{knowledge_text[:6000]}

返工意见：
{feedback or "首次生成，无返工意见"}
""".strip()
        data = extract_json_object(spark_chat(prompt))
        script = str(data.get("script") or "视频脚本生成失败，请检查大模型配置。")
        storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), list) else []
        lines = ["## 教学短视频脚本", script, "", "## 分镜表"]
        for item in storyboard:
            lines.append(
                f"- **{item.get('time', '片段')}**：画面：{item.get('visual', '')}；旁白：{item.get('narration', '')}；字幕：{item.get('subtitle', '')}"
            )
        video_url = ""
        if script and "生成失败" not in script:
            video_url = see_dance_generate(script[:1800])
            if video_url and str(video_url).lstrip().startswith("{"):
                lines.extend(["", "## 视频生成状态", video_url])
            elif video_url:
                lines.extend(["", "## 视频生成结果", video_url])
        return {
            "resource_type": "video",
            "title": str(data.get("title") or "软件工程教学短视频脚本"),
            "content": "\n".join(lines),
            "video_url": video_url,
            "storyboard": storyboard,
            "knowledge_points": data.get("knowledge_points") or [str(context.get("weak_points") or "软件工程核心知识")],
            "personalization": str(data.get("personalization") or f"围绕学生薄弱点“{context.get('weak_points', '')}”设计短时长分镜。"),
            "format": "video_storyboard",
            "agent_name": self.__class__.__name__,
        }
