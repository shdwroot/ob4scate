"""Validated, hot-reloadable text-obfuscation policy service."""

import asyncio
import logging
from pathlib import Path

import regex
import spacy
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from policy_engine.sensitive_data import (
    CORE_DETECTORS,
    DEFAULT_EXAMPLE_TEXT,
    DEFAULT_SENSITIVE_DATA,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="Policy Engine", version="0.6.0")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "assets"), name="static")
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

MAX_TEXT_LENGTH = 100_000
REGEX_TIMEOUT_SECONDS = 0.05

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    logger.warning("spaCy model en_core_web_sm is unavailable; name redaction disabled")


class PatternRule(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_ -]{0,63}$")
    pattern: str = Field(min_length=1, max_length=512)

    @field_validator("pattern")
    @classmethod
    def compile_pattern(cls, value: str) -> str:
        try:
            regex.compile(value, flags=regex.IGNORECASE)
        except regex.error as exc:
            raise ValueError(f"Invalid regular expression: {exc}") from exc
        return value


class PolicyRules(BaseModel):
    obfuscate_email: bool = True
    obfuscate_phone: bool = True
    obfuscate_names: bool = True
    obfuscate_locations: bool = True
    custom_patterns: list[PatternRule] = Field(default_factory=list, max_length=100)


class PolicyUpdate(BaseModel):
    obfuscate_email: bool | None = None
    obfuscate_phone: bool | None = None
    obfuscate_names: bool | None = None
    obfuscate_locations: bool | None = None
    custom_patterns: list[PatternRule] | None = Field(default=None, max_length=100)


class TextData(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


policy_rules = PolicyRules(
    custom_patterns=[
        PatternRule(name=definition["name"], pattern=definition["pattern"])
        for definition in DEFAULT_SENSITIVE_DATA
    ]
)
policy_lock = asyncio.Lock()

POLICY_CATALOG = [
    *CORE_DETECTORS,
    *[
        {
            "name": definition["name"],
            "category": definition["category"],
            "description": definition["description"],
            "example": definition["example"],
        }
        for definition in DEFAULT_SENSITIVE_DATA
    ],
]
POLICY_CATEGORY_COUNT = len({detector["category"] for detector in POLICY_CATALOG})

EMAIL_PATTERN = regex.compile(r"\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = regex.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\w)|(?<!\w)\+?\d{10,15}(?!\w)"
)


def _apply_policies(text: str, rules: PolicyRules) -> str:
    for rule in rules.custom_patterns:
        text = regex.sub(
            rule.pattern,
            f"[{rule.name.upper().replace(' ', '_')}]",
            text,
            flags=regex.IGNORECASE,
            timeout=REGEX_TIMEOUT_SECONDS,
        )
    if rules.obfuscate_email:
        text = EMAIL_PATTERN.sub("[EMAIL]", text, timeout=REGEX_TIMEOUT_SECONDS)
    if rules.obfuscate_phone:
        text = PHONE_PATTERN.sub("[PHONE]", text, timeout=REGEX_TIMEOUT_SECONDS)
    if (rules.obfuscate_names or rules.obfuscate_locations) and nlp is not None:
        doc = nlp(text)
        replacements = []
        for entity in doc.ents:
            if rules.obfuscate_names and entity.label_ == "PERSON":
                replacements.append((entity.start_char, entity.end_char, "[PERSON]"))
            elif rules.obfuscate_locations and entity.label_ in {"FAC", "GPE", "LOC"}:
                replacements.append((entity.start_char, entity.end_char, "[LOCATION]"))
        for start, end, replacement in reversed(replacements):
            text = text[:start] + replacement + text[end:]
    return text


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok" if nlp is not None else "degraded",
        "ner_model": "available" if nlp is not None else "unavailable",
    }


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="admin", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/rules", response_model=PolicyRules)
async def get_rules() -> PolicyRules:
    async with policy_lock:
        return policy_rules.model_copy(deep=True)


@app.get("/catalog")
async def get_catalog() -> list[dict[str, str]]:
    return POLICY_CATALOG


@app.get("/admin", include_in_schema=False)
async def admin_ui(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "catalog": POLICY_CATALOG,
            "category_count": POLICY_CATEGORY_COUNT,
            "example_text": DEFAULT_EXAMPLE_TEXT,
            "ner_available": nlp is not None,
            "rules": policy_rules.model_dump(mode="json"),
        },
    )


@app.patch("/rules", response_model=PolicyRules)
async def update_rules(new_rules: PolicyUpdate) -> PolicyRules:
    global policy_rules
    changes = new_rules.model_dump(exclude_none=True)
    async with policy_lock:
        policy_rules = PolicyRules.model_validate(
            {**policy_rules.model_dump(mode="python"), **changes}
        )
        return policy_rules.model_copy(deep=True)


@app.post("/enforce")
async def enforce_policies(data: TextData) -> dict[str, str]:
    async with policy_lock:
        rules = policy_rules.model_copy(deep=True)
    try:
        obfuscated = await run_in_threadpool(_apply_policies, data.text, rules)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A policy pattern exceeded the execution time limit",
        ) from exc
    return {"obfuscated": obfuscated}
