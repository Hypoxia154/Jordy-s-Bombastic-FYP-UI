from datetime import datetime
from typing import List, Dict, Any

from app.db.sqlite import db

class RBACRepository:
    def log_access(self, username: str, role: str, endpoint: str, method: str, action: str) -> None:
        """Logs a Casbin authorization decision (ALLOWED or DENIED)."""
        now = datetime.utcnow().isoformat()
        with db() as conn:
            conn.execute(
                """
                INSERT INTO rbac_access_logs 
                (timestamp, username, role, endpoint, method, action) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, username, role, endpoint, method, action)
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Aggregates RBAC metrics for the dashboard."""
        with db() as conn:
            # total requests by role
            role_counts = conn.execute(
                "SELECT role, COUNT(*) as count FROM rbac_access_logs GROUP BY role"
            ).fetchall()
            role_distribution = {row["role"]: row["count"] for row in role_counts}

            # daily allowed vs denied (last 7 days approximation)
            # group by date (yyyy-mm-dd), action
            daily_stats = conn.execute(
                """
                SELECT substr(timestamp, 1, 10) as date, action, COUNT(*) as count 
                FROM rbac_access_logs 
                GROUP BY date, action 
                ORDER BY date DESC 
                LIMIT 14
                """
            ).fetchall()
            
            trend_data = []
            for row in daily_stats:
                trend_data.append({
                    "date": row["date"],
                    "action": row["action"],
                    "count": row["count"]
                })

            # overall totals
            total_allowed = conn.execute("SELECT COUNT(*) FROM rbac_access_logs WHERE action='ALLOWED'").fetchone()[0]
            total_denied = conn.execute("SELECT COUNT(*) FROM rbac_access_logs WHERE action='DENIED'").fetchone()[0]

            # recent denials (for the audit log table)
            recent_denials = conn.execute(
                """
                SELECT timestamp, username, role, endpoint, method 
                FROM rbac_access_logs 
                WHERE action='DENIED' 
                ORDER BY id DESC 
                LIMIT 10
                """
            ).fetchall()
            
            denial_list = [dict(row) for row in recent_denials]

            return {
                "total_allowed": total_allowed,
                "total_denied": total_denied,
                "role_distribution": role_distribution,
                "trend_data": trend_data,
                "recent_denials": denial_list
            }
