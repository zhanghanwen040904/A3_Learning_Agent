from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── 认证 ──

class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ── 学生画像 ──

class KnowledgeBase(BaseModel):
    digital_logic: Optional[str] = None
    assembly: Optional[str] = None
    computer_architecture: Optional[str] = None


class StudentProfile(BaseModel):
    """学生画像 — 至少 6 个维度"""
    major: Optional[str] = None
    grade: Optional[str] = None
    course_goal: Optional[str] = None
    knowledge_base: Optional[dict] = Field(default_factory=dict)
    weak_points: List[str] = Field(default_factory=list)
    learning_preference: List[str] = Field(default_factory=list)
    pace: Optional[str] = None
    resource_preference: List[str] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    user_id: str
    profile: StudentProfile
    updated_at: Optional[datetime] = None


class ProfileUpdateRequest(BaseModel):
    profile: StudentProfile


# ── 资源生成 ──

class ResourceGenerateRequest(BaseModel):
    user_id: str = "demo_user"
    course: str = "computer_organization"
    knowledge_point: str
    resource_types: list[str]  # ["doc", "mindmap", "quiz", "code", "video_script"]


class ResourceItem(BaseModel):
    type: str
    title: str
    content: str  # Markdown / Mermaid / JSON string


class ReviewResult(BaseModel):
    passed: bool
    notes: list[str] = []


class ResourceGenerateResponse(BaseModel):
    resources: list[ResourceItem]
    review: ReviewResult
