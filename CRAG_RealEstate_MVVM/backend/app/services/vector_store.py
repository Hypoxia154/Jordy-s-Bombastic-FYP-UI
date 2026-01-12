import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import SimpleDirectoryReader

# Use environment variable or default to local Docker Qdrant
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")


def get_client():
    return QdrantClient(url=QDRANT_URL)


def get_index(collection_name: str):
    """Loads the Index from Qdrant"""
    client = get_client()
    try:
        # Check if collection exists
        if not client.collection_exists(collection_name):
            return None

        vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Load index from the storage context
        return VectorStoreIndex.from_vector_store(
            vector_store, storage_context=storage_context
        )
    except Exception as e:
        print(f"❌ Error loading index: {e}")
        return None


def upload_file(file_path: str, collection_name: str):
    """Ingests a file into Qdrant"""
    client = get_client()

    # Load data using LlamaIndex SimpleDirectoryReader
    documents = SimpleDirectoryReader(input_files=[file_path]).load_data()

    # Setup Vector Store
    vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Create Index (ingest data)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
    )
    return "Success"