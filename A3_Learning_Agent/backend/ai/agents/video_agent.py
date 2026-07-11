import json
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from ai.json_utils import extract_json_object
from ai.llm_api import generate_teaching_video, llm_chat
from config import config
from .base_agent import AgentSpec


VIDEO_SUFFIXES = {".mp4", ".webm", ".ogg", ".mov", ".m4v"}
VIDEO_KEYWORDS = {
    "软件危机": ["软件危机"],
    "软件工程": ["软件工程", "方法学"],
    "软件生命周期": ["软件生命周期", "生命周期"],
    "瀑布模型": ["瀑布模型"],
    "原型模型": ["原型", "快速原型"],
    "增量模型": ["增量模型"],
    "螺旋模型": ["螺旋模型"],
    "喷泉模型": ["喷泉模型"],
    "可行性研究": ["可行性研究", "成本效益"],
    "数据流图": ["数据流图", "数据字典", "系统流程图"],
    "需求分析": ["需求分析", "需求收集", "验证需求", "形式化说明"],
    "ER图": ["ER", "ER图", "分析建模"],
    "总体设计": ["总体设计", "设计过程", "设计原理"],
    "耦合": ["耦合"],
    "内聚": ["内聚"],
    "结构化设计": ["结构化设计", "变换分析", "事务分析"],
    "详细设计": ["详细设计", "PAD", "判定树", "PDL", "程序复杂度"],
    "用户界面设计": ["用户界面设计"],
    "编码": ["编码"],
    "软件测试": ["测试", "单元测试", "系统测试", "确认测试"],
    "软件维护": ["维护", "维护工作"],
}


class VideoAgent:
    """教学短视频资源生成智能体。"""

    def __init__(self):
        self.role = "多模态视频制作师"
        self.goal = "基于核心知识点生成聚焦、简短、适合本科生学习的教学短视频"
        self.agent = AgentSpec(
            role=self.role,
            goal=self.goal,
            tools=["local_video_retrieval", "generate_teaching_video"],
            input_schema="核心知识点文本",
            output_schema="教学短视频 URL",
        )

    @staticmethod
    def _video_dir() -> Path:
        return Path(config.RAG_SOURCE_DIR).parent / "videos"

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(ch.lower() for ch in str(value or "") if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")

    def _iter_videos(self) -> list[Path]:
        video_dir = self._video_dir()
        if not video_dir.exists():
            return []
        return sorted(path for path in video_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES)

    def _match_local_video(self, context: Dict[str, Any], task_plan: Dict[str, Any], knowledge_text: str) -> Path | None:
        videos = self._iter_videos()
        if not videos:
            return None
        query_parts = [
            context.get("weak_points"),
            context.get("study_goal"),
            context.get("current_need"),
            context.get("stage_title"),
            " ".join(context.get("stage_points") or []),
            task_plan.get("goal"),
            task_plan.get("selected_primary_knowledge_title"),
            " ".join(task_plan.get("selected_knowledge_points") or []),
            knowledge_text[:500],
        ]
        query = self._normalize(" ".join(str(part or "") for part in query_parts))
        scored = []
        for video in videos:
            name = self._normalize(video.stem)
            score = 0
            if name and name in query:
                score += 80
            for topic, keywords in VIDEO_KEYWORDS.items():
                topic_norm = self._normalize(topic)
                topic_hit = topic_norm and topic_norm in query
                keyword_hits = sum(1 for keyword in keywords if self._normalize(keyword) in query)
                filename_hits = sum(1 for keyword in keywords if self._normalize(keyword) in name)
                if topic_hit and filename_hits:
                    score += 50
                score += min(keyword_hits, 3) * filename_hits * 10
            for token in ["需求", "设计", "测试", "维护", "编码", "模型", "数据流", "可行性", "耦合", "内聚"]:
                token_norm = self._normalize(token)
                if token_norm in query and token_norm in name:
                    score += 8
            if score > 0:
                scored.append((score, video))
        if not scored:
            return videos[0]
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return scored[0][1]

    @staticmethod
    def _local_video_url(video_path: Path) -> str:
        return f"/api/knowledge/video?path={quote(video_path.name)}"

    def _local_video_resource(self, video_path: Path, context: Dict[str, Any]) -> Dict[str, Any]:
        title = video_path.stem
        weak_points = context.get("weak_points") or context.get("stage_title") or "课程核心知识"
        content = "\n".join(
            [
                f"## 已匹配本地课程视频：{title}",
                "",
                f"视频文件：`{video_path.name}`",
                "",
                "## 学习建议",
                f"- 先观看该视频，重点关注与“{weak_points}”相关的概念、流程和例子。",
                "- 观看后回到学习路径中的讲解文档和练习题，完成概念复述与自测。",
                "- 如果视频内容偏基础，可继续查看拓展阅读和代码案例完成迁移应用。",
            ]
        )
        return {
            "resource_type": "video",
            "title": title,
            "content": content,
            "video_url": self._local_video_url(video_path),
            "storyboard": [],
            "knowledge_points": context.get("stage_points") or [str(weak_points)],
            "personalization": f"优先从本地课程视频库中匹配与“{weak_points}”相关的视频，避免等待实时视频生成。",
            "format": "local_video",
            "agent_name": self.__class__.__name__,
        }

    def generate(
        self,
        context: Dict[str, Any],
        knowledge_text: str,
        task_plan: Dict[str, Any],
        feedback: str = "",
    ) -> Dict[str, Any]:
        local_video = self._match_local_video(context, task_plan, knowledge_text)
        if local_video:
            return self._local_video_resource(local_video, context)

        prompt = f"""
[RESOURCE:VIDEO]
你是多模态视频制作师。请为学生设计 60 秒以内教学短视频。
学生上下文：{json.dumps(context, ensure_ascii=False)}
任务计划：{json.dumps(task_plan, ensure_ascii=False)}
教材依据：{knowledge_text[:2400]}
返工意见：{feedback or '无'}
严格返回 JSON：
{{"title":"","script":"完整旁白","storyboard":[{{"time":"0-10s","visual":"画面","narration":"旁白","subtitle":"字幕"}}],"knowledge_points":[],"personalization":""}}
分镜至少 4 段，必须同时包含画面、旁白和字幕，并体现学生专业、短板与学习偏好。
""".strip()
        data = extract_json_object(llm_chat(prompt))
        script = str(data.get("script") or "视频脚本生成失败")
        storyboard = data.get("storyboard") if isinstance(data.get("storyboard"), list) else []
        lines = ["## 教学视频脚本", script, "", "## 分镜表"]
        for item in storyboard:
            lines.append(
                f"- **{item.get('time', '片段')}**｜画面：{item.get('visual', '')}｜旁白：{item.get('narration', '')}｜字幕：{item.get('subtitle', '')}"
            )
        video_url = generate_teaching_video(script) if script and script != "视频脚本生成失败" else ""
        if video_url.startswith("{"):
            video_url = ""
        if video_url:
            lines.extend(["", "## 视频生成结果", video_url])
        return {
            "resource_type": "video",
            "title": str(data.get("title") or "个性化 AI 教学短视频"),
            "content": "\n".join(lines),
            "video_url": video_url,
            "storyboard": storyboard,
            "knowledge_points": data.get("knowledge_points") or [str(context.get("weak_points") or "课程核心知识")],
            "personalization": str(
                data.get("personalization")
                or f"围绕学生薄弱点“{context.get('weak_points', '')}”设计短时长分镜。"
            ),
            "format": "video_storyboard",
            "agent_name": self.__class__.__name__,
        }
