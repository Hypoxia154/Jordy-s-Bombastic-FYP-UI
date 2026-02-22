import sys
import os
import json
from unittest.mock import MagicMock

# Add project root and backend to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'backend'))

# Mock llama_index.llms.ollama before importing CRAGService
# We need to mock these modules because we might not have them installed or want to run LLM
sys.modules['llama_index.llms.ollama'] = MagicMock()
sys.modules['llama_index.core'] = MagicMock()
sys.modules['llama_index.core.retrievers'] = MagicMock()
sys.modules['llama_index.core.postprocessor'] = MagicMock()
sys.modules['app.services.vector_store'] = MagicMock()

# Now we can safely import CRAGService class structure, 
# but we need to supply the mocked LLM behavior at runtime or subclass for testing.
# Actually, since we want to test the *logic* inside the methods we added, 
# we should verify that `_try_extract_chart_data` works with correct regex.

from backend.app.services.crag_service import CRAGService

def test_chart_extraction():
    print("Testing Chart Extraction...")
    service = CRAGService()
    service.llm = MagicMock()
    
    # Mock LLM response for a chart query
    mock_json_response = '''
    Sure, here is the data:
    [
        {"label": "Kuala Lumpur", "value": 1500},
        {"label": "Penang", "value": 1200}
    ]
    '''
    service.llm.complete.return_value.text = mock_json_response

    # Test case 1: Query with keywords
    data = service._try_extract_chart_data("context", "Show me a chart of average rent")
    
    if data and len(data) == 2 and data[0]['label'] == "Kuala Lumpur":
        print("✅ Chart extraction passed")
    else:
        print(f"❌ Chart extraction failed. Got: {data}")

    # Test case 2: Query without keywords
    data_none = service._try_extract_chart_data("context", "What is the rent?")
    if data_none is None:
         print("✅ Keyword check passed (returned None)")
    else:
         print(f"❌ Keyword check failed. Got: {data_none}")

def test_query_normalization():
    print("\nTesting Query Normalization...")
    service = CRAGService()
    q = service._normalize_query("What should included in the contract?")
    if "should be included" in q:
        print("✅ Query normalization passed")
    else:
        print(f"❌ Query normalization failed. Got: {q}")

if __name__ == "__main__":
    try:
        test_chart_extraction()
        test_query_normalization()
    except Exception as e:
        print(f"❌ Test crashed: {e}")
