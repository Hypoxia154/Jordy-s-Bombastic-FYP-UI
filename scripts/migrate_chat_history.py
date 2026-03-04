"""Optional migration helper:
Imports your old `chat_history.db` into the new `backend/app.db`.

Usage:
  python scripts/migrate_chat_history.py --old path/to/chat_history.db --new backend/app.db
"""

import argparse
import sqlite3
from datetime import datetime


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="Path to old chat_history.db")
    ap.add_argument("--new", required=True, help="Path to new app.db")
    args = ap.parse_args()

    old = sqlite3.connect(args.old)
    old.row_factory = sqlite3.Row

    new = sqlite3.connect(args.new)
    new.row_factory = sqlite3.Row
    new.execute("PRAGMA foreign_keys = ON;")

    sessions = old.execute("SELECT * FROM chat_sessions").fetchall()
    msgs = old.execute("SELECT * FROM chat_messages").fetchall()

    for s in sessions:
        u = s["username"]
        exists = new.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone()
        if not exists:
            new.execute(
                "INSERT INTO users (username,password_hash,role,name,email,created_at,last_login) VALUES (?,?,?,?,?,?,?)",
                (u, "!", "staff", u, f"{u}@example.com", datetime.now().strftime("%Y-%m-%d"), None),
            )

    id_map = {}
    for s in sessions:
        cur = new.execute(
            "INSERT INTO chat_sessions (username,title,created_at) VALUES (?,?,?)",
            (s["username"], s["title"], s["created_at"]),
        )
        id_map[s["id"]] = cur.lastrowid

    for m in msgs:
        new.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
            (id_map[m["session_id"]], m["role"], m["content"], m["timestamp"]),
        )

    new.commit()
    old.close()
    new.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
