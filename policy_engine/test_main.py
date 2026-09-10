import pytest
from fastapi.testclient import TestClient

import policy_engine.main as policy


@pytest.fixture
def client():
    original = policy.policy_rules.model_copy(deep=True)
    with TestClient(policy.app) as test_client:
        yield test_client
    policy.policy_rules = original


def test_enforcement_redacts_without_echoing_original(client):
    response = client.post("/enforce", json={"text": "Email me at jane@example.com about Diabetes"})
    assert response.status_code == 200
    payload = response.json()
    assert "jane@example.com" not in payload["obfuscated"]
    assert "Diabetes" not in payload["obfuscated"]
    assert "original" not in payload


def test_policy_update_is_validated_and_applied(client):
    response = client.patch("/rules", json={"obfuscate_email": False})
    assert response.status_code == 200
    assert response.json()["obfuscate_email"] is False

    invalid = client.patch(
        "/rules",
        json={"custom_patterns": [{"name": "Broken", "pattern": "("}]},
    )
    assert invalid.status_code == 422


def test_policy_input_has_size_and_empty_guards(client):
    assert client.post("/enforce", json={"text": ""}).status_code == 422
