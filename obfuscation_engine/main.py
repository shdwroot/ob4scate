"""PII detection and redaction service."""

import logging
import re

import spacy
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
app = FastAPI(title="Local LLM Obfuscation Engine", version="0.2.0")

EMAIL_PATTERN = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
MAX_TEXT_LENGTH = 100_000

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    logger.warning("spaCy model en_core_web_sm is unavailable; regex redaction only")


class SanitizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


def _sanitize(text: str) -> str:
    sanitized = EMAIL_PATTERN.sub("[EMAIL]", text)
    if nlp is None:
        return sanitized

    doc = nlp(sanitized)
    for entity in reversed(doc.ents):
        sanitized = (
            sanitized[: entity.start_char] + f"[{entity.label_}]" + sanitized[entity.end_char :]
        )
    return sanitized


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "ner_model": "available" if nlp is not None else "unavailable",
    }


@app.post("/sanitize")
async def sanitize_text(data: SanitizeRequest) -> dict[str, str]:
    """Return redacted text without echoing the original sensitive value."""
    sanitized = await run_in_threadpool(_sanitize, data.text)
    return {"sanitized": sanitized}
