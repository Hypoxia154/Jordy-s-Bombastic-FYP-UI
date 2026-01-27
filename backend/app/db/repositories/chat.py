from dataclasses import dataclass
from datetime import datetime
import json

from app.db.sqlite import db


@dataclass
class ChatSession:
    id: int
    username: str
    title: str
    created_at: str


class ChatRepository:
    def list_sessions(self, username: str) -> list[dict]:
        with db() as conn:
            rows = conn.execute(
                "SELECT id, username, title, created_at FROM chat_sessions WHERE username=? ORDER BY id DESC",
                (username,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_session(self, username: str, first_user_message: str) -> ChatSession:
        title = (
            (first_user_message[:40] + "...")
            if len(first_user_message) > 40
            else first_user_message
        )
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO chat_sessions (username, title, created_at) VALUES (?,?,?)",
                (username, title, created_at),
            )
            sid = cur.lastrowid
        return ChatSession(id=sid, username=username, title=title, created_at=created_at)

    def session_belongs_to_user(self, session_id: int, username: str) -> bool:
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM chat_sessions WHERE id=? AND username=?",
                (session_id, username),
            ).fetchone()
            return row is not None

    def get_messages(self, session_id: int) -> list[dict]:
        with db() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp, sources, confidence FROM chat_messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            out: list[dict] = []
            for r in rows:
                item = dict(r)
                if item.get("sources"):
                    try:
                        item["sources"] = json.loads(item["sources"])
                    except Exception:
                        item["sources"] = [item["sources"]]
                else:
                    item["sources"] = []
                out.append(item)
            return out

    def append_message(self, session_id: int, payload: dict) -> dict:
        role = payload["role"]
        content = payload["content"]
        ts = payload.get("timestamp") or datetime.now().isoformat()
        sources = payload.get("sources")
        confidence = payload.get("confidence")

        sources_json = (
            json.dumps(sources)
            if isinstance(sources, list)
            else (json.dumps([sources]) if sources else None)
        )

        with db() as conn:
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp, sources, confidence) VALUES (?,?,?,?,?,?)",
                (session_id, role, content, ts, sources_json, confidence),
            )
            msg_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        return {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": ts,
            "sources": sources or [],
            "confidence": confidence,
        }

    def clear_sessions(self, username: str) -> None:
        with db() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE username=?", (username,))
