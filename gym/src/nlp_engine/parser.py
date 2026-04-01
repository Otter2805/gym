import requests
import json
import os

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ai-engine:11434")

def parse_workout_text(user_input: str):
    payload = {
        "model": "llama3.2:3b", 
        "prompt": f"Extract workout data: '{user_input}'. Respond ONLY in JSON: {{\"exercise\": str, \"sets\": int, \"reps\": int, \"weight\": float}}",
        "format": "json",
        "stream": False
    }
    
    try:
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        response.raise_for_status()
        return json.loads(response.json()['response'])
    except Exception as e:
        print(f"NLP Error: {e}")
        return None