from app.db.sqlite import db


class DocsRepository:
    def search_keyword(self, query: str, limit: int = 5) -> list[dict]:
        q = f"%{query.lower()}%"
        with db() as conn:
            rows = conn.execute(
                "SELECT id, title, content, tags FROM knowledge_docs WHERE lower(title) LIKE ? OR lower(content) LIKE ? LIMIT ?",
                (q, q, limit),
            ).fetchall()
            return [dict(r) for r in rows]
