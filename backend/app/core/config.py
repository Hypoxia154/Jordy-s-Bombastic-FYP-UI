from pydantic import BaseModel
import os

class Settings(BaseModel):
    database_path: str = os.getenv("SQLITE_PATH", "app.db")
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "720"))
    cors_allow_origins: list[str] = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

    # AI Configuration
    LLM_MODEL: str = "phi3:mini"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Database
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    COLLECTION_NAME: str = "crag_llamaindex"

settings = Settings()
