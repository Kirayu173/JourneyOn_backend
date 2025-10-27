from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用程序设置，从环境变量加载。

    提供整个应用程序使用的类型化配置。
    """

    DATABASE_URL: str = "postgresql+psycopg2://app:secret@localhost:5432/journeyon"
    REDIS_URL: str | None = "redis://localhost:6379/0"
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "kb_entries"
    VECTOR_DIM: int = 1024
    VECTOR_DISTANCE: str = "Cosine"

    # LLM 提供商配置
    LLM_PROVIDER: str = "ollama"  # 支持: "ollama", "zhipu"
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 0.5
    LLM_REQUEST_TIMEOUT: float = 30.0
    LLM_STREAM_TIMEOUT: float = 60.0
    OLLAMA_CHAT_MODEL: str = "gpt-oss:120b-cloud"
    ZHIPU_API_KEY: str | None = None
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_CHAT_MODEL: str = "glm-4.5-x"

    SECRET_KEY: str = "dev-secret-key"
    LOG_LEVEL: str = "info"

    # 嵌入模型提供商
    ENABLE_EMBEDDING: bool = False
    EMBEDDING_PROVIDER: str = "ollama"  # 支持: "ollama", "openai"
    OLLAMA_URL: str | None = None  # 例如: http://localhost:11434
    OLLAMA_EMBED_MODEL: str = "bge-m3:latest"
    OLLAMA_RERANK_MODEL: str | None = None
    OLLAMA_RERANK_ENABLED: bool = True
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-large"
    EMBEDDING_CONCURRENCY: int = 4
    EMBEDDING_TIMEOUT: float = 30.0

    # API 安全配置
    RATE_LIMIT_PER_MINUTE: int = 60

    # 日志文件记录和轮转
    LOG_TO_FILE: bool = False
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_ROTATION_POLICY: str = "time"  # 可选: "time", "size"
    LOG_ROTATION_WHEN: str = "D"  # 用于 TimedRotatingFileHandler
    LOG_ROTATION_INTERVAL: int = 1
    LOG_BACKUP_COUNT: int = 7
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 用于基于大小的轮转

    # 文件存储
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "storage"

    # Memory layer (develop_mem0) integration
    MEMORY_ENABLED: bool = False
    MEMORY_INFER: bool = False
    MEMORY_COLLECTION_NAME: str = "memories"
    MEMORY_HISTORY_DB_PATH: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
