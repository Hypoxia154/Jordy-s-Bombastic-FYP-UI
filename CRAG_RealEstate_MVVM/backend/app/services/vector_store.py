from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol
import hashlib
import math


@dataclass
class RetrievedChunk:
    source: str
    text: str
    score: float


class VectorStore(Protocol):
    def upsert(self, doc_id: str, text: str, metadata: dict) -> None: ...

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]: ...


class HashEmbeddingProvider:
    """Deterministic embedding fallback (no external ML dependencies).
    Replace with a real embedding model later."""

    def embed(self, text: str, dim: int = 128) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        out = []
        for i in range(dim):
            b = h[i % len(h)]
            out.append((b - 128) / 128.0)
        norm = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / norm for x in out]


class SQLiteKeywordStore:
    def __init__(self, docs_repo):
        self.docs_repo = docs_repo

    def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        return

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        rows = self.docs_repo.search_keyword(query, limit=top_k)
        chunks = []
        for r in rows:
            chunks.append(
                RetrievedChunk(source=r["title"], text=r["content"], score=0.5)
            )
        return chunks


class QdrantVectorStore:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection: str = "knowledge",
        embedding_provider: Optional[HashEmbeddingProvider] = None,
    ):
        self.host = host
        self.port = port
        self.collection = collection
        self.embedding = embedding_provider or HashEmbeddingProvider()

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams
        except Exception as e:
            raise RuntimeError(
                "qdrant-client not installed. Install qdrant-client to use QdrantVectorStore."
            ) from e

        self.client = QdrantClient(host=self.host, port=self.port)

        existing = [c.name for c in self.client.get_collections().collections]
        if collection not in existing:
            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=128, distance=Distance.COSINE),
            )

    def upsert(self, doc_id: str, text: str, metadata: dict) -> None:
        vector = self.embedding.embed(text, dim=128)
        self.client.upsert(
            collection_name=self.collection,
            points=[{"id": doc_id, "vector": vector, "payload": {"text": text, **metadata}}],
        )

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        qv = self.embedding.embed(query, dim=128)
        hits = self.client.search(self.collection, query_vector=qv, limit=top_k)
        out: list[RetrievedChunk] = []
        for h in hits:
            payload = h.payload or {}
            out.append(
                RetrievedChunk(
                    source=str(payload.get("title") or payload.get("source") or h.id),
                    text=str(payload.get("text") or ""),
                    score=float(h.score or 0.0),
                )
            )
        return out
