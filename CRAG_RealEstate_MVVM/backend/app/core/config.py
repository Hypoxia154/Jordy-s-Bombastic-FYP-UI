from pydantic import BaseModel
import os

class Settings(BaseModel):
    database_path: str = os.getenv("SQLITE_PATH", "app.db")
    token_ttl_minutes: int = int(os.getenv("TOKEN_TTL_MINUTES", "720"))
    cors_allow_origins: list[str] = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")

settings = Settings()
