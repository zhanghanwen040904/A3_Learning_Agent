"""学生画像管理 — 抽取、存储、更新"""
import json
import re
from typing import Optional

from sqlalchemy.orm import Session

from ..models import UserProfile
from ..schemas import StudentProfile
from ..llm_client import SparkLLM

EXTRACTION_PROMPT = """请从以下学生对话中，提取学习画像信息，输出严格 JSON（不要 Markdown 代码块）。

画像维度：
- major: 专业背景
- grade: 年级
- course_goal: 学习目标
- knowledge_base: 各前置课程的掌握程度 (对象，如 {"数字逻辑":"中等"})
- weak_points: 薄弱知识点列表
- learning_preference: 学习偏好列表（如 ["图解","例题","代码示例"]）
- pace: 学习节奏
- resource_preference: 偏好资源类型列表（如 ["思维导图","练习题"]）

学生对话:
{conversation}

仅输出 JSON:"""


def extract_profile_from_text(text: str) -> StudentProfile:
    """用大模型从对话文本中抽取学生画像，失败时返回空画像不抛异常"""
    try:
        llm = SparkLLM()
        prompt = EXTRACTION_PROMPT.format(conversation=text)
        raw = llm.chat(prompt)

        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group()) if match else {}

        return StudentProfile(**data)
    except Exception as e:
        print(f"[Profile] 画像抽取失败，返回空画像: {e}")
        return StudentProfile()


def get_profile(db: Session, user_id: int) -> Optional[StudentProfile]:
    """从数据库加载学生画像"""
    row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if row and row.profile_json:
        data = json.loads(row.profile_json)
        return StudentProfile(**data)
    return None


def save_profile(db: Session, user_id: int, profile: StudentProfile) -> UserProfile:
    """保存或更新学生画像"""
    row = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    profile_json = profile.model_dump_json(ensure_ascii=False)

    if row:
        row.profile_json = profile_json
    else:
        row = UserProfile(user_id=user_id, profile_json=profile_json)
        db.add(row)

    db.commit()
    db.refresh(row)
    return row


def update_profile_from_conversation(db: Session, user_id: int, message: str) -> StudentProfile:
    """
    从用户消息中抽取画像，与已有画像合并后持久化。

    Returns:
        合并后的完整画像
    """
    # 1. 从消息中抽取新画像
    new_profile = extract_profile_from_text(message)

    # 2. 加载已有画像
    existing = get_profile(db, user_id)

    # 3. 合并：新值覆盖旧值，列表去重合并
    if existing:
        merged = existing.model_dump()
        new_data = new_profile.model_dump(exclude_unset=True, exclude_none=True)
        for key, value in new_data.items():
            if isinstance(value, list) and isinstance(merged.get(key), list):
                merged[key] = list(set(merged[key] + value))
            elif value:
                merged[key] = value
        merged_profile = StudentProfile(**merged)
    else:
        merged_profile = new_profile

    # 4. 持久化
    save_profile(db, user_id, merged_profile)
    return merged_profile
