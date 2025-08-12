from fastapi import FastAPI
import re
import spacy

app = FastAPI(title="Local LLM Obfuscation Engine", version="0.1.0")

# Load spaCy English NER model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None  # Will require download in production


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/sanitize")
async def sanitize_text(data: dict):
    """
    Detects potential PII using regex + spaCy NER.
    MVP: Returns an obfuscated version with placeholders.
    """
    text = data.get("text", "")

    # Basic regex obfuscation example - replace email addresses
    sanitized = re.sub(r"\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", "[EMAIL]", text)

    # spaCy NER obfuscation if model loaded
    if nlp:
        doc = nlp(sanitized)
        for ent in doc.ents:
            sanitized = sanitized.replace(ent.text, f"[{ent.label_}]")

    return {"original": text, "sanitized": sanitized}