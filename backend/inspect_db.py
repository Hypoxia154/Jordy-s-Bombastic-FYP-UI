import sys
import os

# Add the current directory to sys.path so we can import app modules
sys.path.append(os.getcwd())

from qdrant_client import QdrantClient
from app.core.config import settings

def inspect_db():
    print("--- Inspecting Qdrant Database ---")
    client = QdrantClient(url=settings.QDRANT_URL)
    
    collection_name = "crag_llamaindex"
    
    try:
        # Check count
        count = client.count(collection_name).count
        print(f"Total Vectors: {count}")
        
        if count == 0:
            print("Database is empty!")
            return

        # Scroll first 3 points
        points, _ = client.scroll(
            collection_name=collection_name,
            limit=3,
            with_payload=True,
            with_vectors=False
        )

        for i, point in enumerate(points):
            print(f"\n[Point {i+1}] ID: {point.id}")
            payload = point.payload
            
            # Key info for RAG
            text = payload.get("_node_content", "{}")
            # LlamaIndex stores text in a JSON string inside _node_content usually, or just 'text' field
            # Check for direct text field first (LlamaIndex 0.10+ style)
            doc_text = payload.get("text") or payload.get("page_content")
            
            # If not found, try parsing _node_content
            if not doc_text and "_node_content" in payload:
                 import json
                 try:
                     node_data = json.loads(payload["_node_content"])
                     doc_text = node_data.get("text", "")
                 except:
                     doc_text = "Parsing failed"

            print(f"Metadata: {payload.get('metadata', 'None')}")
            print(f"Content Preview: {doc_text[:200]}...")  # First 200 chars
            print(f"Content Length: {len(doc_text) if doc_text else 0}")
            
    except Exception as e:
        print(f"Error connecting to Qdrant: {e}")

if __name__ == "__main__":
    inspect_db()
