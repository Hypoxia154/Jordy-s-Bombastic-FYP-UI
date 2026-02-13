from typing import List
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, Settings as LlamaSettings
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import settings


class VectorService:
    def __init__(self):
        print(" [VectorStore] Initializing Embedding Model & Settings...")

        # 1. Tuning for BGE-Small (Max 512 tokens)
        LlamaSettings.chunk_size = 512
        LlamaSettings.chunk_overlap = 50

        # Load Embedding Model locally
        LlamaSettings.embed_model = HuggingFaceEmbedding(model_name=settings.EMBEDDING_MODEL)
        print(" [VectorStore] Embedding Model Loaded.")

        self.client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.COLLECTION_NAME

        if not self.client.collection_exists(self.collection_name):
            print(f" [VectorStore] Collection '{self.collection_name}' not found. Creating it...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=384,
                    distance=models.Distance.COSINE
                )
            )

        self.vector_store = QdrantVectorStore(client=self.client, collection_name=self.collection_name)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

    def get_index(self):
        return VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context
        )

    def ingest_document(self, file_path: str, file_name_override: str = None):
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        
        # Override filename metadata if provided
        if file_name_override:
            for doc in documents:
                doc.metadata["file_name"] = file_name_override
                
        VectorStoreIndex.from_documents(
            documents,
            storage_context=self.storage_context,
            show_progress=True
        )
        return f"Successfully ingested {len(documents)} pages from {file_name_override or file_path}."

    def clear_database(self):
        self.client.delete_collection(self.collection_name)
        return "Database cleared! Please re-ingest your documents."

    def list_ingested_files(self) -> List[str]:
        """
        Scrolls through the Qdrant database to find unique file names in metadata.
        """
        try:
            # Scroll to get unique filenames (Limit to 1000 points for now)
            # ideally we would use a payload based group-by or specialized request
            response = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000, 
                with_payload=True,
                with_vectors=False
            )

            seen_files = set()
            points, _ = response

            for point in points:
                payload = point.payload or {}
                # Handle various LlamaIndex metadata structures
                f_name = payload.get("file_name") or payload.get("metadata", {}).get("file_name")
                
                # Fallback: check _node_content json string
                if not f_name and "_node_content" in payload:
                    import json
                    try:
                        node_data = json.loads(payload["_node_content"])
                        f_name = node_data.get("metadata", {}).get("file_name")
                    except:
                        pass

                if f_name:
                    # Clean path to just show filename
                    clean_name = f_name.split("/")[-1].split("\\")[-1]
                    seen_files.add(clean_name)

            return sorted(list(seen_files))
        except Exception as e:
            print(f" [VectorStore] List Files Error: {e}")
            return []

    def delete_file(self, filename: str) -> bool:
        """
        Deletes all points associated with a specific filename.
        """
        try:
            print(f" [VectorStore] Deleting file: {filename}")
            
            # Create Filter for file_name
            # LlamaIndex typically puts it in 'file_name' or 'metadata.file_name'
            # We will try both common locations by OR-ing them if possible, 
            # or just deleting by the key we found most reliable in list_files.
            # For simplicity, we assume 'file_name' is accessible as a payload field 
            # (LlamaIndex usually promotes metadata to payload columns in Qdrant).
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="file_name",
                                match=models.MatchValue(value=filename)
                            )
                        ]
                    )
                )
            )
            
            # Also try 'metadata.file_name' just in case structure varies
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="metadata.file_name",
                                match=models.MatchValue(value=filename)
                            )
                        ]
                    )
                )
            )
            
            return True
        except Exception as e:
            print(f" [VectorStore] Delete Error: {e}")
            return False
