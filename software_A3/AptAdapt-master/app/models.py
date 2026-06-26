from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    """学生画像 — JSON 字符串存储，支持灵活字段"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    profile_json = Column(Text, nullable=True)          # 完整画像 JSON
    raw_conversation = Column(Text, nullable=True)      # 原始对话记录
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
