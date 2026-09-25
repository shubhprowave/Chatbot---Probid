from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Postgres
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@postgres:5432/ragdb"

    # LLM (Groq — OpenAI-compatible API; free tier)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "qwen/qwen3.8-27b"
    LLM_MODEL_FAST: str = "qwen/qwen3.8-27b"
    LLM_CTX: int = 6144
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 320

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    EMBEDDING_MAX_LEN: int = 1024

    # Reranker
    RERANK_MODEL: str = "BAAI/bge-reranker-base"
    RERANK_MAX_LEN: int = 512

    # Retrieval (optimized for speed)
    TOP_K_DENSE: int = 30      # Reduced from 40
    TOP_K_SPARSE: int = 30     # Reduced from 40
    TOP_K_HYBRID: int = 15     # Reduced from 20
    TOP_K_RERANK: int = 4      # Reduced from 5
    RRF_K: int = 60
    HNSW_EF_SEARCH: int = 80   # Reduced from 100 for faster search

    # Cache
    REDIS_URL: str = "redis://redis:6379"
    CACHE_TTL: int = 3600

    # Auth
    ADMIN_TOKEN: str = "change-me"
    CORS_ORIGINS: str = "https://yourcompany.com"

    # Tender database (MySQL)
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "probid"
    TENDER_RESULT_LIMIT: int = 10
    TENDER_ENABLED: bool = True

    @property
    def cors_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()