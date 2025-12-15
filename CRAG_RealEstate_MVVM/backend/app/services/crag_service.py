from dataclasses import dataclass

from app.db.repositories.docs import DocsRepository
from app.services.vector_store import RetrievedChunk, SQLiteKeywordStore


@dataclass
class CRAGResult:
    answer: str
    sources: list[str]
    confidence: float


class CRAGService:
    """Working CRAG baseline:

    - Retrieval: SQLite keyword retrieval (default)
    - Generation: deterministic, evidence-first composition

    Swap retrieval/generation later without changing API or Streamlit MVVM code.
    """

    def __init__(self):
        self.docs_repo = DocsRepository()
        self.retriever = SQLiteKeywordStore(self.docs_repo)

    def answer(self, question: str, user_role: str) -> CRAGResult:
        chunks = self.retriever.search(question, top_k=5)
        if not chunks:
            return CRAGResult(
                answer=(
                    "I couldn't find a relevant snippet in the current knowledge base. "
                    "Try rephrasing or add more documents."
                ),
                sources=[],
                confidence=0.55,
            )

        answer = self._compose_answer(question, chunks, user_role)
        sources = [c.source for c in chunks[:3] if c.source]
        confidence = min(
            0.88,
            0.65 + 0.05 * len(sources) + (0.03 if user_role in {"admin", "master"} else 0.0),
        )
        return CRAGResult(answer=answer, sources=sources, confidence=confidence)

    def _compose_answer(self, question: str, chunks: list[RetrievedChunk], user_role: str) -> str:
        bullets = []
        for c in chunks[:3]:
            snippet = c.text.strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "..."
            bullets.append(f"- {snippet} ({c.source})")

        role_line = "" if user_role == "staff" else f"\n\n*(Access: {user_role.upper()})*"
        return "**Answer (based on retrieved knowledge):**\n\n" + "\n".join(bullets) + role_line
