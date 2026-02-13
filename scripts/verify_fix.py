import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def login():
    # Assuming default admin credentials from README
    payload = {"username": "admin", "password": "admin123"}
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=payload)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print(f"Login successful. Token: {token[:10]}...")
            return token
        else:
            print(f"Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

def test_query(token):
    headers = {"Authorization": f"Bearer {token}"}
    # Session
    session_res = requests.post(f"{BASE_URL}/chat/sessions", json={"first_user_message": "Hello"}, headers=headers)
    if session_res.status_code != 200:
        print(f"Failed to create session: {session_res.text}")
        return
    
    session_id = session_res.json()["id"]
    print(f"Created session {session_id}")

    # Query that might have triggered a chart
    query_payload = {
        "question": "visualize the rent trends",
        "session_id": session_id
    }
    
    print(f"Sending query: {query_payload['question']}")
    start = time.time()
    res = requests.post(f"{BASE_URL}/crag/query", json=query_payload, headers=headers)
    duration = time.time() - start
    
    if res.status_code == 200:
        data = res.json()
        print(f"Response received in {duration:.2f}s")
        print(f"Answer: {data.get('answer')[:100]}...")
        if data.get("chart_data") is None:
            print("SUCCESS: chart_data is None as expected.")
        else:
            print(f"FAILURE: chart_data is present: {data.get('chart_data')}")
            
        if "visualize" in data.get('answer').lower() and len(data.get('answer')) < 50:
             print("Warning: Answer might be too short/generic, possibly due to removed logic fallback.")
    else:
        print(f"Query failed: {res.text}")

if __name__ == "__main__":
    token = login()
    if token:
        test_query(token)
