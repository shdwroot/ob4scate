"""Regression coverage for every default sensitive-data detector."""

import pytest

import policy_engine.main as policy
from policy_engine.sensitive_data import DEFAULT_EXAMPLE_TEXT, DEFAULT_SENSITIVE_DATA


def deterministic_rules() -> policy.PolicyRules:
    return policy.PolicyRules(
        obfuscate_email=False,
        obfuscate_phone=False,
        obfuscate_names=False,
        obfuscate_locations=False,
        custom_patterns=[
            policy.PatternRule(name=definition["name"], pattern=definition["pattern"])
            for definition in DEFAULT_SENSITIVE_DATA
        ],
    )


@pytest.mark.parametrize(
    "definition",
    DEFAULT_SENSITIVE_DATA,
    ids=[definition["name"] for definition in DEFAULT_SENSITIVE_DATA],
)
def test_each_default_detector_redacts_its_documented_example(definition):
    protected = policy._apply_policies(definition["example"], deterministic_rules())

    marker = f"[{definition['name']}]"
    assert marker in protected
    assert definition["example"] not in protected


def test_default_example_redacts_every_sensitive_value_without_nlp():
    protected = policy._apply_policies(DEFAULT_EXAMPLE_TEXT, deterministic_rules())

    for marker in (
        "PERSON_NAME",
        "POSTAL_ADDRESS",
        "DATE_OF_BIRTH",
        "ZA_ID_NUMBER",
        "PASSPORT_NUMBER",
        "CREDIT_CARD",
        "IBAN",
        "INSURANCE_IDENTIFIER",
        "MEDICAL_RECORD",
        "HEALTH_DATA",
        "IPV4_ADDRESS",
        "DEVICE_IDENTIFIER",
        "GPS_COORDINATES",
        "API_SECRET",
        "PASSWORD_OR_PIN",
        "URL",
    ):
        assert f"[{marker}]" in protected


def test_core_email_and_phone_detectors_redact_realistic_values():
    rules = policy.PolicyRules(custom_patterns=[])
    protected = policy._apply_policies(
        "Email jane@example.com or call +27 82 123 4567.",
        rules,
    )

    assert protected == "Email [EMAIL] or call [PHONE]."


def test_phone_detector_does_not_redact_short_numbers():
    rules = policy.PolicyRules(
        obfuscate_email=False,
        obfuscate_names=False,
        obfuscate_locations=False,
        custom_patterns=[],
    )

    assert policy._apply_policies("Order 12345 has 3 items", rules) == ("Order 12345 has 3 items")
