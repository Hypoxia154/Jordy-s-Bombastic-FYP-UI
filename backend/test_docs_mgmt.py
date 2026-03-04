import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from app.services.crag_service import CRAGService

def test_docs_management():
    print("--- Testing Document Management API Logic ---")
    
    # Mock the VectorService to avoid hitting real DB or needing it running
    service = CRAGService()
    service.vector_service = MagicMock()
    
    # 1. Test List
    print("\n[Test 1] List Documents")
    mock_files = ["contract.pdf", "policy.txt"]
    service.vector_service.list_ingested_files.return_value = mock_files
    
    result = service.list_documents()
    print(f"Result: {result}")
    
    if result == mock_files:
        print("✅ List Documents Passed")
    else:
        print("❌ List Documents Failed")
        
    # 2. Test Delete
    print("\n[Test 2] Delete Document")
    service.vector_service.delete_file.return_value = True
    
    success = service.delete_document("contract.pdf")
    print(f"Delete Success: {success}")
    
    if success:
        print("✅ Delete Document Passed")
        service.vector_service.delete_file.assert_called_with("contract.pdf")
    else:
        print("❌ Delete Document Failed")

if __name__ == "__main__":
    test_docs_management()
