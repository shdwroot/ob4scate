from fastapi import FastAPI
import requests
import os
import time
import json

app = FastAPI(title="LiteLLM Integration Service", version="0.1.0")

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://ollama:11434")


@app.get("/health")
async def health_check():
    max_retries = 5
    delay = 2
    reachable = False
    for _ in range(max_retries):
        try:
            response = requests.get(f"{LITELLM_BASE_URL}/api/version", timeout=2)
            if response.status_code == 200:
                reachable = True
                break
        except requests.RequestException:
            time.sleep(delay)
    return {
        "status": "ok",
        "litellm_connection": "reachable" if reachable else "unreachable"
    }


@app.post("/route")
async def route_to_llm(data: dict):
    """
    Forwards sanitized prompt to LiteLLM unified API gateway or Ollama directly.
    Adds multi-LLM intelligent routing based on prompt content or provided routing rules.
    """
    prompt = data.get("prompt")
    model = data.get("model")  # no default, will be resolved by routing if not provided
    options = data.get("options", {"num_ctx": 32768, "temperature": 0.7})
    routing_rules = data.get("routing_rules", {})  # e.g., {"contains": {"finance": "gpt-4-finance"}}

    # Simple example of intelligent routing
    if not model:
        selected_model = None
        if routing_rules.get("contains"):
            for keyword, target_model in routing_rules["contains"].items():
                if keyword.lower() in prompt.lower():
                    selected_model = target_model
                    break
        if not selected_model:
            # Default fallback model
            selected_model = "mistral"
        model = selected_model

    try:
        r = requests.post(
            f"{LITELLM_BASE_URL}/api/generate",
            json={"model": model, "prompt": prompt, "options": options},
            stream=True,
            timeout=300
        )

        try:
            # Attempt to parse as single JSON (non-streaming)
            return {"status_code": r.status_code, "model": model, "response": r.json()}
        except json.JSONDecodeError:
            # Handle streaming JSONL
            output_text = ""
            for line in r.iter_lines():
                if line:
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            output_text += obj["response"]
                    except json.JSONDecodeError:
                        continue
            return {"status_code": r.status_code, "model": model, "response": output_text}

    except requests.RequestException as e:
        return {"error": str(e), "model": model}