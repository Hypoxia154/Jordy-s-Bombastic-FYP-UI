from pydantic import BaseModel
import os
from dotenv import load_dotenv

# load .env from the backend directory (where this app runs from)
load_dotenv()

class Settings(BaseModel):
    database_path: str = os.getenv("SQLITE_PATH", "app.db")
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "720"))
    cors_allow_origins: list[str] = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

    # ai configuration
    LLM_MODEL: str = "phi3:3.8b-instruct"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # database
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    COLLECTION_NAME: str = "crag_llamaindex"

    # openai api (for chart extraction)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"


settings = Settings()
