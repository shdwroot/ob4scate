"""Validated asynchronous connector for the configured local LLM service."""

import os
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="LLM Integration Service", version="0.2.0")

LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://ollama:11434").rstrip("/")
if urlparse(LITELLM_BASE_URL).scheme not in {"http", "https"}:
    raise RuntimeError("LITELLM_BASE_URL must use http or https")


class RouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, min_length=1, max_length=128)
    options: dict[str, Any] = Field(default_factory=lambda: {"num_ctx": 32768, "temperature": 0.7})
    routing_rules: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"num_ctx", "temperature", "top_k", "top_p", "seed"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unsupported options: {', '.join(sorted(unknown))}")
        return value

    @field_validator("routing_rules")
    @classmethod
    def validate_routing_rules(cls, value: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        if set(value) - {"contains"}:
            raise ValueError("Only the 'contains' routing rule is supported")
        contains = value.get("contains", {})
        if len(contains) > 50:
            raise ValueError("At most 50 routing rules are allowed")
        if any(not keyword or len(keyword) > 128 for keyword in contains):
            raise ValueError("Routing keywords must contain 1 to 128 characters")
        if any(not model or len(model) > 128 for model in contains.values()):
            raise ValueError("Routing model names must contain 1 to 128 characters")
        return value


def _select_model(request: RouteRequest) -> str:
    if request.model:
        return request.model
    prompt = request.prompt.casefold()
    for keyword, target_model in request.routing_rules.get("contains", {}).items():
        if keyword.casefold() in prompt:
            return target_model
    return os.getenv("DEFAULT_LLM_MODEL", "mistral")


@app.get("/health")
async def health_check() -> dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{LITELLM_BASE_URL}/api/version")
            response.raise_for_status()
    except httpx.HTTPError:
        return {"status": "degraded", "llm_connection": "unreachable"}
    return {"status": "ok", "llm_connection": "reachable"}


@app.post("/route")
async def route_to_llm(data: RouteRequest) -> dict[str, Any]:
    model = _select_model(data)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=5.0)) as client:
            response = await client.post(
                f"{LITELLM_BASE_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": data.prompt,
                    "options": data.options,
                    "stream": False,
                },
            )
            response.raise_for_status()
            upstream_payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider request failed",
        ) from exc
    return {"model": model, "response": upstream_payload}
