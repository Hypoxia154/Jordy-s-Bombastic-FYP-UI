from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any, Dict

from app.db.sqlite import db


@dataclass
class ChatSession:
    id: int
    username: str
    title: str
    created_at: str
    pinned: int = 0


class ChatRepository:
    def list_sessions(self, username: str) -> list[dict]:
        with db() as conn:
            rows = conn.execute(
                """
                SELECT id, username, title, created_at, pinned
                FROM chat_sessions
                WHERE username=?
                ORDER BY pinned DESC, id DESC
                """,
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
                """
                INSERT INTO chat_sessions (username, title, created_at, pinned, state_json)
                VALUES (?, ?, ?, 0, ?)
                """,
                (username, title, created_at, json.dumps({}, ensure_ascii=False)),
            )
            sid = cur.lastrowid

        return ChatSession(
            id=sid,
            username=username,
            title=title,
            created_at=created_at,
            pinned=0,
        )

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
                """
                SELECT role, content, timestamp, sources, confidence, bleu_score, evidence
                FROM chat_messages
                WHERE session_id=?
                ORDER BY id ASC
                """,
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

                if item.get("evidence"):
                    try:
                        item["evidence"] = json.loads(item["evidence"])
                    except Exception:
                        item["evidence"] = []
                else:
                    item["evidence"] = []

                if item.get("bleu_score") is None:
                    item["bleu_score"] = 0.0

                out.append(item)

            return out

    def append_message(self, session_id: int, payload: dict) -> dict:
        role = payload["role"]
        content = payload["content"]
        ts = payload.get("timestamp") or datetime.now().isoformat()
        sources = payload.get("sources")
        confidence = payload.get("confidence")
        bleu_score = payload.get("bleu_score")
        evidence = payload.get("evidence")

        sources_json = (
            json.dumps(sources, ensure_ascii=False)
            if isinstance(sources, list)
            else (json.dumps([sources], ensure_ascii=False) if sources else None)
        )

        evidence_json = (
            json.dumps(evidence, ensure_ascii=False)
            if isinstance(evidence, list)
            else None
        )

        with db() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages
                (session_id, role, content, timestamp, sources, confidence, bleu_score, evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, role, content, ts, sources_json, confidence, bleu_score, evidence_json),
            )
            msg_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        return {
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": ts,
            "sources": sources or [],
            "confidence": confidence,
            "bleu_score": bleu_score if bleu_score is not None else 0.0,
            "evidence": evidence or [],
        }

    def clear_sessions(self, username: str) -> None:
        with db() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE username=?", (username,))

    def rename_session(self, session_id: int, username: str, title: str) -> bool:
        with db() as conn:
            cur = conn.execute(
                "UPDATE chat_sessions SET title=? WHERE id=? AND username=?",
                (title, session_id, username),
            )
            return cur.rowcount > 0

    def delete_session(self, session_id: int, username: str) -> bool:
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM chat_sessions WHERE id=? AND username=?",
                (session_id, username),
            ).fetchone()
            if not row:
                return False

            conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
            return True

    def pin_session(self, session_id: int, username: str, pinned: bool) -> bool:
        with db() as conn:
            row = conn.execute(
                "SELECT 1 FROM chat_sessions WHERE id=? AND username=?",
                (session_id, username),
            ).fetchone()
            if not row:
                return False

            conn.execute(
                "UPDATE chat_sessions SET pinned=? WHERE id=?",
                (1 if pinned else 0, session_id),
            )
            return True

    def get_session_state(self, session_id: int) -> dict:
        with db() as conn:
            row = conn.execute(
                "SELECT state_json FROM chat_sessions WHERE id=?",
                (session_id,),
            ).fetchone()

            if not row:
                return {}

            raw = row["state_json"]
            if not raw:
                return {}

            try:
                return json.loads(raw)
            except Exception:
                return {}

    def set_session_state(self, session_id: int, state: Dict[str, Any]) -> None:
        state_json = json.dumps(state, ensure_ascii=False)
        with db() as conn:
            conn.execute(
                "UPDATE chat_sessions SET state_json=? WHERE id=?",
                (state_json, session_id),
            )

    def patch_session_state(self, session_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        state = self.get_session_state(session_id)
        state.update(updates)
        self.set_session_state(session_id, state)
        return state

    def update_session_state(self, session_id: int, patch: dict) -> None:
        state = self.get_session_state(session_id)
        if not isinstance(state, dict):
            state = {}

        for k, v in (patch or {}).items():
            state[k] = v

        with db() as conn:
            conn.execute(
                "UPDATE chat_sessions SET state_json=? WHERE id=?",
                (json.dumps(state, ensure_ascii=False), session_id),
            )