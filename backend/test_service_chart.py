from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.crag_service import CRAGService
from llama_index.core.schema import TextNode

def test_chart_generation():
    print("--- Testing Chart Generation ---")
    
    # 1. Initialize Service
    service = CRAGService()
    
    # 2. Mock Retriever to return dummy data
    mock_retriever = MagicMock()
    mock_node = TextNode(
        text="The average rental price in Kuala Lumpur is RM2000 in Jan, RM2100 in Feb, and RM2200 in March.",
        metadata={"file_name": "market_report.pdf"}
    )
    mock_retriever.retrieve.return_value = [mock_node]
    
    # Patch the retriever creation inside the method? 
    # Hard to patch inside the method without deeper mocking.
    # Instead, let's just use the `chart_prompt` and LLM directly to simulate what happens inside per the code logic.
    
    context_str = mock_node.text
    query = "Show me the rental trend in KL"
    
    print(f"Query: {query}")
    print(f"Context: {context_str}")
    
    prompt = service.chart_prompt.format(context_str=context_str, query_str=query)
    print("\n[Prompt Sent to LLM]:")
    print(prompt)
    
    print("\n[Waiting for LLM Response]...")
    response = service.llm.complete(prompt).text.strip()
    
    print("\n[Raw LLM Response]:")
    print(response)
    
    # 3. Try to Parse exactly like the service code
    import json
    try:
        # Robust JSON extraction
        if "```json" in response:
            clean_response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            clean_response = response.split("```")[1].split("```")[0].strip()
        else:
            clean_response = response

        # Remove any text before first { or after last }
        start = clean_response.find('{')
        end = clean_response.rfind('}') + 1
        if start != -1 and end > start:
            clean_response = clean_response[start:end]
            
        print(f"\n[Cleaned JSON]:\n{clean_response}")
        
        chart_data = json.loads(clean_response)
        print("\n[Parsed JSON]:")
        print(json.dumps(chart_data, indent=2))
        
        # Validate structure
        if "data" not in chart_data or "labels" not in chart_data.get("data", {}):
            print("\n[Validation Failed]: Missing 'data' or 'labels'")
        else:
            print("\n[Validation Success]: Chart data conforms to schema.")
            
    except Exception as e:
        print(f"\n[Parsing Error]: {e}")

if __name__ == "__main__":
    test_chart_generation()
