from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Provides typed configuration used across the application.
    """

    DATABASE_URL: str = "postgresql+psycopg2://app:secret@localhost:5432/journeyon"
    REDIS_URL: str | None = "redis://localhost:6379/0"
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "kb_entries"
    VECTOR_DIM: int = 1024
    VECTOR_DISTANCE: str = "Cosine"

    SECRET_KEY: str = "dev-secret-key"
    LOG_LEVEL: str = "info"

    # Embedding providers
    ENABLE_EMBEDDING: bool = False
    EMBEDDING_PROVIDER: str = "ollama"  # Supported: "ollama", "openai"
    OLLAMA_URL: str | None = None  # e.g. http://localhost:11434
    OLLAMA_EMBED_MODEL: str = "bge-m3:latest"
    OLLAMA_RERANK_MODEL: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-large"

    # API safety
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging to file and rotation
    LOG_TO_FILE: bool = False
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_ROTATION_POLICY: str = "time"  # one of: "time", "size"
    LOG_ROTATION_WHEN: str = "D"  # for TimedRotatingFileHandler
    LOG_ROTATION_INTERVAL: int = 1
    LOG_BACKUP_COUNT: int = 7
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # for size-based rotation

    # File storage
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "storage"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
