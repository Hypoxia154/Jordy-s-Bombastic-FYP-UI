from typing import List, Dict, Any, Optional
from datetime import datetime
from app.db.sqlite import db

class LogsRepository:
    def log_error(
        self,
        level: str,
        endpoint: Optional[str],
        username: Optional[str],
        request_payload: Optional[str],
        error_message: str,
        traceback_str: Optional[str]
    ) -> None:
        """Insert a new error or system log into the database."""
        timestamp = datetime.now().isoformat()
        with db() as conn:
            conn.execute(
                """
                INSERT INTO system_logs (
                    timestamp, level, endpoint, username, request_payload, error_message, traceback
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, level, endpoint, username, request_payload, error_message, traceback_str)
            )

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch the most recent system logs."""
        with db() as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, level, endpoint, username, request_payload, error_message, traceback
                FROM system_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def clear_logs(self) -> None:
        """Clear all logs from the database."""
        with db() as conn:
            conn.execute("DELETE FROM system_logs")
