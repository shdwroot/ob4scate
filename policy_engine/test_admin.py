from fastapi.testclient import TestClient

from policy_engine.main import app

client = TestClient(app)


def test_admin_serves_page_rules_and_static_assets():
    """Regression: the hardcoded proxy root path made every static asset return 404."""
    admin_response = client.get("/admin")
    rules_response = client.get("/rules")
    asset_response = client.get("/static/assets/css/black-dashboard.min.css")

    assert admin_response.status_code == 200
    assert "Policy Engine Admin" in admin_response.text
    assert rules_response.status_code == 200
    assert rules_response.json()["obfuscate_email"] is True
    assert asset_response.status_code == 200
    assert "text/css" in asset_response.headers["content-type"]
