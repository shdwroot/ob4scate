from fastapi.testclient import TestClient

from policy_engine.main import POLICY_CATALOG, POLICY_CATEGORY_COUNT, app

client = TestClient(app)


def test_admin_serves_complete_policy_dashboard():
    admin_response = client.get("/admin")
    rules_response = client.get("/rules")

    assert admin_response.status_code == 200
    assert "Ob4scate Policy Engine" in admin_response.text
    assert "Redaction example" in admin_response.text
    assert "Sensitive-data detector catalog" in admin_response.text
    assert f">{len(POLICY_CATALOG)}<" in admin_response.text
    assert f">{POLICY_CATEGORY_COUNT}<" in admin_response.text
    for detector in POLICY_CATALOG:
        assert detector["name"] in admin_response.text
    assert rules_response.status_code == 200
    assert rules_response.json()["obfuscate_email"] is True


def test_root_redirects_to_admin_without_a_proxy_prefix():
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "admin"


def test_catalog_api_exposes_the_same_complete_catalog():
    response = client.get("/catalog")

    assert response.status_code == 200
    assert response.json() == POLICY_CATALOG
