import os
from fastapi import FastAPI
from pydantic import BaseModel
import re
import spacy

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

app = FastAPI(title="Policy Engine", version="0.4.0", root_path="/policy")

# Mount static files from assets directory
# Correctly mount static assets from the project root so it works inside Docker
assets_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
app.mount("/static", StaticFiles(directory=assets_path), name="static")

# Templates
# Build absolute path from repo root to support both standalone and mounted execution
# Determine absolute path regardless of being run standalone or via gateway_proxy
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
templates_path = os.path.join(BASE_DIR, "templates")
# Always check existence and fallback if necessary
if not os.path.exists(os.path.join(templates_path, "admin.html")):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alt_path = os.path.join(repo_root, "policy_engine", "templates")
    if os.path.exists(os.path.join(alt_path, "admin.html")):
        templates_path = alt_path
templates = Jinja2Templates(directory=templates_path)

# Load spaCy model for NER
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None

class TextData(BaseModel):
    text: str

policy_rules = {
    "obfuscate_email": True,
    "obfuscate_phone": True,
    "obfuscate_names": True,
    "custom_patterns": [
        {"name": "CreditCard", "pattern": r"\b(?:\d[ -]*?){13,16}\b"},
        {"name": "Passport", "pattern": r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b"},  # General passport pattern
        {"name": "SA_ID", "pattern": r"\b\d{6}\s?\d{4}\s?\d{3}\b"},  # South African ID number pattern
        {"name": "PolicyNumber", "pattern": r"\b[A-Z]{2,5}\d{5,10}\b"},
        {"name": "MemberNumber", "pattern": r"\b\d{5,15}\b"},
        {"name": "MedicalInfo", "pattern": r"\b(?:HIV|AIDS|Diabetes|Cancer|Hypertension)\b"},
        {"name": "VehicleReg", "pattern": r"\b[A-Z]{2,3}\s?\d{3,4}\s?[A-Z]{2,3}\b"}
    ]
}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/rules")
async def get_rules():
    return policy_rules

@app.get("/admin", include_in_schema=False)
async def admin_ui(request: Request):
    """
    Serves an HTML admin UI for viewing and updating policy rules.
    """
    return templates.TemplateResponse("admin.html", {"request": request, "rules": policy_rules})

@app.post("/rules")
async def update_rules(new_rules: dict):
    global policy_rules
    policy_rules.update(new_rules)
    return {"status": "updated", "rules": policy_rules}

@app.post("/enforce")
async def enforce_policies(data: TextData):
    """
    Applies policy rules to text data for obfuscation in real-time.
    Uses regex, custom patterns, and spaCy NER if enabled.
    """
    text = data.text
    # Email obfuscation
    if policy_rules.get("obfuscate_email", False):
        text = re.sub(r"\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", "[EMAIL]", text)
    # Phone obfuscation
    if policy_rules.get("obfuscate_phone", False):
        text = re.sub(r"\b(?:\+?(\d{1,3})[-.●]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b", "[PHONE]", text)
    # Names via spaCy NER
    if policy_rules.get("obfuscate_names", False) and nlp:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                text = text.replace(ent.text, "[NAME]")
    # Custom patterns
    for pattern in policy_rules.get("custom_patterns", []):
        text = re.sub(pattern["pattern"], f"[{pattern['name'].upper()}]", text, flags=re.IGNORECASE)

    return {"original": data.text, "obfuscated": text}