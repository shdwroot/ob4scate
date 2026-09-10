import sqlite3

import pytest

import audit_logging.main as audit


@pytest.fixture
def audit_database(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_SIGNING_KEY", "test-signing-key-with-at-least-32-characters")
    monkeypatch.setattr(audit, "DB_PATH", tmp_path / "audit.db")
    audit._initialize_database()
    return audit.DB_PATH


def test_audit_chain_detects_tampering(audit_database):
    first = audit._store_event(audit.AuditLog(event_type="login", event_data={"ok": True}))
    second = audit._store_event(
        audit.AuditLog(event_type="policy.update", event_data={"version": 2})
    )
    assert first[0] == 1
    assert second[0] == 2
    assert audit._verify_chain() == (True, None)

    with sqlite3.connect(audit_database) as connection:
        connection.execute("UPDATE audit_logs SET event_data = ? WHERE id = 1", ('{"ok":false}',))
    assert audit._verify_chain() == (False, 1)


def test_audit_log_limit_is_bounded(audit_database):
    from fastapi.testclient import TestClient

    with TestClient(audit.app) as client:
        assert client.get("/logs?limit=0").status_code == 422
        assert client.get("/logs?limit=1001").status_code == 422
