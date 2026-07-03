import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env", override=True)


def _load_settings_env() -> None:
    settings_path = PROJECT_ROOT / "settings.json"
    if not settings_path.exists():
        return
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return
    env = data.get("env") if isinstance(data, dict) else None
    if not isinstance(env, dict):
        return
    for key, value in env.items():
        if key and value is not None and not os.getenv(str(key)):
            os.environ[str(key)] = str(value)


_load_settings_env()


@dataclass
class Config:
    """全局配置。"""

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

    ANTHROPIC_AUTH_TOKEN: str = os.getenv("ANTHROPIC_AUTH_TOKEN", "")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "")
    ANTHROPIC_SMALL_FAST_MODEL: str = os.getenv("ANTHROPIC_SMALL_FAST_MODEL", "")

    BAILIAN_API_KEY: str = os.getenv("BAILIAN_API_KEY", "")
    BAILIAN_BASE_URL: str = os.getenv(
        "BAILIAN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    BAILIAN_MODEL: str = os.getenv("BAILIAN_MODEL", "qwen-plus")

    SEEDANCE_API_KEY: str = os.getenv("SEEDANCE_API_KEY", "")
    SEEDANCE_API_URL: str = os.getenv("SEEDANCE_API_URL", "")

    CONTENT_AUDIT_API_KEY: str = os.getenv("CONTENT_AUDIT_API_KEY", "")
    CONTENT_AUDIT_API_URL: str = os.getenv("CONTENT_AUDIT_API_URL", "")

    RAG_SOURCE_DIR: str = os.getenv(
        "RAG_SOURCE_DIR",
        str(PROJECT_ROOT / "rag_data" / "source_docs"),
    )
    RAG_VECTOR_DIR: str = os.getenv(
        "RAG_VECTOR_DIR",
        str(PROJECT_ROOT / "rag_data" / "vector_db"),
    )
    RAG_EMBEDDING_MODEL: str = os.getenv(
        "RAG_EMBEDDING_MODEL",
        "BAAI/bge-small-zh-v1.5",
    )

    MOCK_AI: bool = os.getenv("MOCK_AI", "false").lower() == "true"

    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "a3_learner_2026_softcup")
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "bailian").lower()
    AI_RETRY_TIMES: int = int(os.getenv("AI_RETRY_TIMES", "3"))
    AI_RETRY_INTERVAL: float = float(os.getenv("AI_RETRY_INTERVAL", "1.2"))
    AI_TIMEOUT: int = int(os.getenv("AI_TIMEOUT", "90"))


config = Config()
