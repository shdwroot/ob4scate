"""Validated, hot-reloadable text-obfuscation policy service."""

import asyncio
import logging
from pathlib import Path

import regex
import spacy
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)
app = FastAPI(title="Policy Engine", version="0.5.0", root_path="/policy")

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
    custom_patterns: list[PatternRule] = Field(default_factory=list, max_length=100)


class PolicyUpdate(BaseModel):
    obfuscate_email: bool | None = None
    obfuscate_phone: bool | None = None
    obfuscate_names: bool | None = None
    custom_patterns: list[PatternRule] | None = Field(default=None, max_length=100)


class TextData(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


policy_rules = PolicyRules(
    custom_patterns=[
        PatternRule(name="CreditCard", pattern=r"\b(?:\d[ -]*?){13,16}\b"),
        PatternRule(name="Passport", pattern=r"\b[A-PR-WYa-pr-wy][1-9]\d\s?\d{4}[1-9]\b"),
        PatternRule(name="SA_ID", pattern=r"\b\d{6}\s?\d{4}\s?\d{3}\b"),
        PatternRule(name="PolicyNumber", pattern=r"\b[A-Z]{2,5}\d{5,10}\b"),
        PatternRule(name="MemberNumber", pattern=r"\b\d{5,15}\b"),
        PatternRule(
            name="MedicalInfo",
            pattern=r"\b(?:HIV|AIDS|Diabetes|Cancer|Hypertension)\b",
        ),
        PatternRule(name="VehicleReg", pattern=r"\b[A-Z]{2,3}\s?\d{3,4}\s?[A-Z]{2,3}\b"),
    ]
)
policy_lock = asyncio.Lock()

EMAIL_PATTERN = regex.compile(r"\b[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE_PATTERN = regex.compile(
    r"\b(?:\+?(\d{1,3})[-.●]?)?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b"
)


def _apply_policies(text: str, rules: PolicyRules) -> str:
    if rules.obfuscate_email:
        text = EMAIL_PATTERN.sub("[EMAIL]", text, timeout=REGEX_TIMEOUT_SECONDS)
    if rules.obfuscate_phone:
        text = PHONE_PATTERN.sub("[PHONE]", text, timeout=REGEX_TIMEOUT_SECONDS)
    if rules.obfuscate_names and nlp is not None:
        doc = nlp(text)
        people = [entity for entity in doc.ents if entity.label_ == "PERSON"]
        for entity in reversed(people):
            text = text[: entity.start_char] + "[NAME]" + text[entity.end_char :]
    for rule in rules.custom_patterns:
        text = regex.sub(
            rule.pattern,
            f"[{rule.name.upper().replace(' ', '_')}]",
            text,
            flags=regex.IGNORECASE,
            timeout=REGEX_TIMEOUT_SECONDS,
        )
    return text


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "ner_model": "available" if nlp is not None else "unavailable",
    }


@app.get("/rules", response_model=PolicyRules)
async def get_rules() -> PolicyRules:
    async with policy_lock:
        return policy_rules.model_copy(deep=True)


@app.get("/admin", include_in_schema=False)
async def admin_ui(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"rules": policy_rules.model_dump(mode="json")},
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
