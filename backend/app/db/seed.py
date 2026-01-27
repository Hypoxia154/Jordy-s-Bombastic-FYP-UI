from datetime import datetime
import os

from app.db.sqlite import db
from app.core.security import hash_password

DEFAULT_DOCS = [
    (
        "Tenancy Deposits (Malaysia typical practice)",
        "Security deposit is often 2 months' rent and a utility deposit is commonly 0.5 month. Refund is subject to deductions for damages beyond fair wear and tear.",
        "tenancy,deposit",
    ),
    (
        "Maintenance Responsibilities",
        "Tenants usually handle minor maintenance (light bulbs, filters). Landlords typically cover major structural, plumbing, electrical issues unless caused by tenant negligence.",
        "maintenance,repairs",
    ),
    (
        "Termination & Notice",
        "Common notice periods are 1-2 months depending on the agreement. Termination usually requires written notice and settlement of outstanding bills.",
        "termination,notice",
    ),
]


def _user_exists(conn, username: str) -> bool:
    return conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone() is not None


def seed_defaults() -> None:
    master_pwd = os.getenv("MASTER_PASSWORD", "master123")
    admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")

    with db() as conn:
        if not _user_exists(conn, "master"):
            conn.execute(
                "INSERT INTO users (username,password_hash,role,name,email,created_at,last_login) VALUES (?,?,?,?,?,?,?)",
                (
                    "master",
                    hash_password(master_pwd),
                    "master",
                    "Master Admin",
                    "master@company.com",
                    datetime.now().strftime("%Y-%m-%d"),
                    None,
                ),
            )
        if not _user_exists(conn, "admin"):
            conn.execute(
                "INSERT INTO users (username,password_hash,role,name,email,created_at,last_login) VALUES (?,?,?,?,?,?,?)",
                (
                    "admin",
                    hash_password(admin_pwd),
                    "admin",
                    "System Administrator",
                    "admin@company.com",
                    datetime.now().strftime("%Y-%m-%d"),
                    None,
                ),
            )

        # Always ensure default docs are present and up-to-date
        for title, content, tags in DEFAULT_DOCS:
            # Check if doc exists by title
            row = conn.execute("SELECT id FROM knowledge_docs WHERE title=?", (title,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE knowledge_docs SET content=?, tags=? WHERE id=?",
                    (content, tags, row["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO knowledge_docs (title,content,tags,created_at) VALUES (?,?,?,?)",
                    (title, content, tags, datetime.now().isoformat()),
                )
