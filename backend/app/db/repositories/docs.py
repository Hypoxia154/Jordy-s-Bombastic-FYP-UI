from app.db.sqlite import db


class DocsRepository:
    def search_keyword(self, query: str, limit: int = 5) -> list[dict]:
        # Split query into terms to improve recall (simple "OR" search)
        terms = [t.strip() for t in query.lower().split() if len(t.strip()) > 2]
        if not terms:
            terms = [query.lower()]

        conditions = []
        params = []
        for term in terms:
            conditions.append("(lower(title) LIKE ? OR lower(content) LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%"])
        
        sql = f"SELECT id, title, content, tags FROM knowledge_docs WHERE {' OR '.join(conditions)} LIMIT ?"
        params.append(limit)

        with db() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
