from app.db.sqlite import db


class DocsRepository:
    def search_keyword(self, query: str, limit: int = 5) -> list[dict]:
        terms = [t.strip() for t in query.lower().split() if len(t.strip()) > 2]
        if not terms:
            terms = [query.lower()]

        conditions = []
        params = []
        for term in terms:
            conditions.append("(lower(title) LIKE ? OR lower(content) LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])

        sql = f"""
        SELECT id, title, content, tags
        FROM knowledge_docs
        WHERE {' OR '.join(conditions)}
        LIMIT ?
        """
        params.append(limit)

        with db() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Document access control
    # ------------------------------------------------------------------
    def get_access(self, file_name: str) -> list[str]:
        with db() as conn:
            rows = conn.execute(
                "SELECT username FROM document_access WHERE file_name=? ORDER BY username ASC",
                (file_name,),
            ).fetchall()
            return [r["username"] for r in rows]

    def set_access(self, file_name: str, usernames: list[str]) -> None:
        with db() as conn:
            conn.execute("DELETE FROM document_access WHERE file_name=?", (file_name,))
            for u in usernames:
                conn.execute(
                    "INSERT OR IGNORE INTO document_access (file_name, username) VALUES (?, ?)",
                    (file_name, u),
                )

    def get_accessible_files(self, username: str, role: str, all_files: list[str]) -> list[str]:
        if role in ("admin", "master"):
            return all_files

        with db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT file_name FROM document_access WHERE username=?",
                (username,),
            ).fetchall()
            assigned = {r["file_name"] for r in rows}

        return [f for f in all_files if f in assigned]