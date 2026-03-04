import requests
import json

url = "http://localhost:11434/api/generate"
payload = {
    "model": "my-real-estate-bot",
    "prompt": "What is the notice period for termination?",
    "stream": False
}

try:
    print("Testing raw model 'my-real-estate-bot'...")
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        res_json = response.json()
        print("Response:", res_json.get("response"))
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect: {e}")
