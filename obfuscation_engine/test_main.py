from fastapi.testclient import TestClient

from .main import app


def test_sanitize_redacts_email_without_echoing_original():
    with TestClient(app) as client:
        response = client.post("/sanitize", json={"text": "Email jane@example.com"})
    assert response.status_code == 200
    assert response.json() == {"sanitized": "Email [EMAIL]"}
    assert "original" not in response.json()


def test_sanitize_rejects_empty_text():
    with TestClient(app) as client:
        response = client.post("/sanitize", json={"text": ""})
    assert response.status_code == 422
