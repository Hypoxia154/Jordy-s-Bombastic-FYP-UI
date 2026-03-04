import sys
import os

# Add backend to path so imports work
sys.path.append(os.path.join(os.getcwd()))

import requests
from app.services.vector_store import VectorService
from app.core.config import settings

def check_ollama():
    print(f"\n[1] Checking Ollama ({settings.LLM_MODEL})...")
    try:
        # Ollama default port 11434
        res = requests.get("http://localhost:11434/")
        if res.status_code == 200:
            print(" - Ollama is RUNNING.")
        else:
            print(f" - Ollama returned status {res.status_code}.")
    except Exception as e:
        print(f" - Ollama NOT detected: {e}")

def check_qdrant_and_content():
    print(f"\n[2] Checking Qdrant & Vector Store Content ({settings.QDRANT_URL})...")
    try:
        vs = VectorService()
        files = vs.list_ingested_files()
        print(f" - Connection Successful.")
        print(f" - Ingested Files Found ({len(files)}):")
        for f in files:
            print(f"   - {f}")
            
        if not files or "No metadata found" in files[0]:
            print("\n[WARNING] No documents found in Vector Store!")
            print(" -> The chatbot works but has NO specific knowledge. It needs 'training' (ingestion).")
    except Exception as e:
        print(f" - Qdrant Connection FAILED: {e}")

if __name__ == "__main__":
    print("=== SYSTEM VERIFICATION ===")
    try:
        check_ollama()
        check_qdrant_and_content()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
