import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Config:
    """全局配置类。

    功能：集中读取应用端口、MySQL、讯飞星火、讯飞 SeeDance、讯飞内容审核、RAG 路径配置。
    输入：环境变量或 backend/.env 文件。
    输出：可被后端模块直接导入的 config 实例。
    """

    APP_NAME: str = "A3 Learning Agent"
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("APP_PORT", "5000"))
    DEBUG: bool = os.getenv("APP_DEBUG", "true").lower() == "true"

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "a3_learning_agent")
    MYSQL_CHARSET: str = os.getenv("MYSQL_CHARSET", "utf8mb4")

    XFYUN_APP_ID: str = os.getenv("XFYUN_APP_ID", "")
    XFYUN_API_KEY: str = os.getenv("XFYUN_API_KEY", "")
    XFYUN_API_SECRET: str = os.getenv("XFYUN_API_SECRET", "")
    XFYUN_SPARK_URL: str = os.getenv("XFYUN_SPARK_URL", "wss://spark-api.xf-yun.com/v3.5/chat")
    XFYUN_SPARK_DOMAIN: str = os.getenv("XFYUN_SPARK_DOMAIN", "generalv3.5")

    SEEDANCE_API_KEY: str = os.getenv("SEEDANCE_API_KEY", "")
    SEEDANCE_API_URL: str = os.getenv("SEEDANCE_API_URL", "")

    CONTENT_AUDIT_API_KEY: str = os.getenv("CONTENT_AUDIT_API_KEY", "")
    CONTENT_AUDIT_API_URL: str = os.getenv("CONTENT_AUDIT_API_URL", "")

    RAG_SOURCE_DIR: str = os.getenv("RAG_SOURCE_DIR", str(PROJECT_ROOT / "rag_data" / "source_docs"))
    RAG_VECTOR_DIR: str = os.getenv("RAG_VECTOR_DIR", str(PROJECT_ROOT / "rag_data" / "vector_db"))
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

    MOCK_AI: bool = os.getenv("MOCK_AI", "false").lower() == "true"

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "a3_learner_2026_softcup")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    AI_RETRY_TIMES: int = int(os.getenv("AI_RETRY_TIMES", "3"))
    AI_RETRY_INTERVAL: float = float(os.getenv("AI_RETRY_INTERVAL", "1.2"))
    AI_TIMEOUT: int = int(os.getenv("AI_TIMEOUT", "90"))


config = Config()
