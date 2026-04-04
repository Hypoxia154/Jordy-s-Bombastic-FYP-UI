from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.init_db import ensure_schema
from app.db.seed import seed_defaults
from app.api.routes import auth, users, chat, crag, logs, rbac
from app.core.deps import get_crag_service
from app.db.sqlite import init_db_migrations

app = FastAPI(title="CRAG Real Estate API", version="1.0.0")

import traceback
import json
from fastapi import Request
from fastapi.responses import JSONResponse

from app.db.repositories.logs import LogsRepository
from app.db.repositories.tokens import TokensRepository

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for 500 crashes to log to the system_logs DB before returning a generic error."""
    endpoint = request.url.path
    traceback_str = traceback.format_exc()
    error_msg = str(exc)

    # try to extract username from authorization header
    username = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        username = TokensRepository().validate_token(token)

    # try to extract request payload
    request_payload = None
    try:
        body_bytes = await request.body()
        if body_bytes:
            # only store valid json payloads to avoid saving huge binary blob uploads
            request_payload = json.dumps(json.loads(body_bytes))
    except Exception:
        pass # Not json or unreadable

    # log to db
    try:
        LogsRepository().log_error(
            level="ERROR",
            endpoint=endpoint,
            username=username,
            request_payload=request_payload,
            error_message=error_msg,
            traceback_str=traceback_str
        )
    except Exception as db_err:
        print(f"Failed to write to system logs: {db_err}")

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. The crash has been logged for administrators."}
    )

@app.on_event("startup")
def _startup() -> None:
    ensure_schema()
    seed_defaults()
    get_crag_service()
    init_db_migrations()# call one time only, after that can remove

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(crag.router, prefix="/crag", tags=["crag"])
app.include_router(logs.router, prefix="/admin/logs", tags=["logs"])
app.include_router(rbac.router, prefix="/admin/rbac", tags=["rbac"])
# trigger reload due to policy.csv change
