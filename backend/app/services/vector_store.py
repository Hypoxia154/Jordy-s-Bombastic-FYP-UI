from __future__ import annotations

import json
import os
from typing import List, Set

from llama_index.core import (
    Settings as LlamaSettings,
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    Document,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings


class VectorService:
    def __init__(self):
        print(" [VectorStore] Initializing Embedding Model & Settings...")

        # chunking tuned for small embedding models like bge-small
        LlamaSettings.chunk_size = 512
        LlamaSettings.chunk_overlap = 50

        # load embedding model locally
        LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=settings.EMBEDDING_MODEL)
        print(" [VectorStore] Embedding Model Loaded.")

        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.COLLECTION_NAME
        self.vector_size = 384

        self._ensure_collection()

        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
        )
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    # core setup
    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            print(f" [VectorStore] Collection '{self.collection_name}' not found. Creating it...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE,
                ),
            )

    def get_index(self):
        self._ensure_collection()
        return VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context,
        )

    # filename helpers
    def _safe_filename(self, name: str) -> str:
        base = os.path.basename(name or "uploaded_file")
        base = base.replace("..", "")
        return base.strip()

    def _candidate_filename_values(self, filename: str) -> List[str]:
        """
        Try both the raw value and basename value, because metadata may contain
        either a clean filename or a full path depending on ingestion path.
        """
        raw = (filename or "").strip()
        base = self._safe_filename(raw)

        values = []
        for v in [raw, base]:
            if v and v not in values:
                values.append(v)
        return values

    def _extract_filename_from_payload(self, payload: dict) -> str:
        payload = payload or {}

        f_name = payload.get("file_name")
        if not f_name and isinstance(payload.get("metadata"), dict):
            f_name = payload["metadata"].get("file_name")

        if not f_name and "_node_content" in payload:
            try:
                node_data = json.loads(payload["_node_content"])
                f_name = (
                    node_data.get("metadata", {}).get("file_name")
                    or node_data.get("file_path")
                )
            except Exception:
                pass

        if not f_name:
            return ""

        return self._safe_filename(str(f_name))

    def _extract_chunk_text_from_payload(self, payload: dict) -> str:
        payload = payload or {}

        chunk_text = payload.get("text") or payload.get("document_text") or ""

        if not chunk_text and "_node_content" in payload:
            try:
                node_data = json.loads(payload["_node_content"])
                chunk_text = (
                    node_data.get("text")
                    or node_data.get("text_resource", {}).get("text", "")
                    or node_data.get("node", {}).get("text", "")
                )
            except Exception:
                pass

        return (chunk_text or "").strip()

    # ingestion
    def ingest_document(self, file_path: str, file_name_override: str = None) -> str:
        """
        Backward-compatible raw-file ingestion.
        Use ingest_text() when text has already been extracted (for example via Docling OCR).
        """
        self._ensure_collection()

        target_filename = self._safe_filename(file_name_override or os.path.basename(file_path))

        try:
            self.delete_file(target_filename)
        except Exception as e:
            print(f" [VectorStore] Warning: could not pre-delete '{target_filename}': {e}")

        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()

        for doc in documents:
            doc.metadata["file_name"] = target_filename

        VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context,
            show_progress=True,
        )

        return f"Successfully ingested {len(documents)} pages from {target_filename}."

    def ingest_text(self, text: str, file_name: str) -> str:
        """
        Ingest already-extracted text directly into Qdrant.
        This is the correct path for Docling/PyPDF extracted content.
        """
        self._ensure_collection()
        target_filename = self._safe_filename(file_name)

        try:
            self.delete_file(target_filename)
        except Exception as e:
            print(f" [VectorStore] Warning: could not pre-delete '{target_filename}': {e}")

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return f"No extractable text found for {target_filename}."

        doc = Document(
            text=cleaned_text,
            metadata={
                "file_name": target_filename,
                "page_label": "doc",
            },
        )

        VectorStoreIndex.from_documents(
            [doc],
            storage_context=self.storage_context,
            show_progress=True,
        )

        return f"Successfully ingested document '{target_filename}' into vector store."

    # collection management
    def clear_database(self) -> str:
        try:
            if self.client.collection_exists(self.collection_name):
                self.client.delete_collection(self.collection_name)
            self._ensure_collection()
            return "Database cleared! Please re-ingest your documents."
        except Exception as e:
            print(f" [VectorStore] Clear Database Error: {e}")
            return "Failed to clear database."

    # scroll helpers
    def _scroll_all_points(self, scroll_filter=None, page_size: int = 200):
        """
        Full pagination over the whole collection.
        """
        all_points = []
        next_offset = None

        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=page_size,
                offset=next_offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=scroll_filter,
            )

            all_points.extend(points)

            if next_offset is None:
                break

        return all_points

    # listing / fallback chunk access
    def list_ingested_files(self) -> List[str]:
        """
        Full pagination across all points to collect unique filenames.
        """
        try:
            seen_files: Set[str] = set()
            points = self._scroll_all_points(page_size=200)

            for point in points:
                payload = point.payload or {}
                f_name = self._extract_filename_from_payload(payload)
                if f_name:
                    seen_files.add(f_name)

            return sorted(seen_files)
        except Exception as e:
            print(f" [VectorStore] List Files Error: {e}")
            return []

    def get_file_chunks(self, filename: str, limit: int = 200) -> List[str]:
        """
        Returns stored text chunks for a specific file by reading Qdrant payloads.
        Useful as a fallback when SQLite doc_texts is empty.
        """
        target_names = set(self._candidate_filename_values(filename))
        chunks: List[str] = []
        seen_chunks: Set[str] = set()

        try:
            points = self._scroll_all_points(page_size=200)

            for point in points:
                payload = point.payload or {}
                stored_name = self._extract_filename_from_payload(payload)

                if stored_name not in target_names:
                    continue

                chunk_text = self._extract_chunk_text_from_payload(payload)
                if chunk_text and chunk_text not in seen_chunks:
                    seen_chunks.add(chunk_text)
                    chunks.append(chunk_text)

                if len(chunks) >= limit:
                    break

        except Exception as e:
            print(f" [VectorStore] Get File Chunks Error: {e}")

        return chunks[:limit]

    # delete by filename
    def delete_file(self, filename: str) -> bool:
        """
        Deletes all points associated with a specific filename.
        """
        target_values = self._candidate_filename_values(filename)

        try:
            print(f" [VectorStore] Deleting file: {filename}")

            for value in target_values:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="file_name",
                                    match=models.MatchValue(value=value),
                                )
                            ]
                        )
                    ),
                )

                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="metadata.file_name",
                                    match=models.MatchValue(value=value),
                                )
                            ]
                        )
                    ),
                )

            return True
        except Exception as e:
            print(f" [VectorStore] Delete Error: {e}")
            return False