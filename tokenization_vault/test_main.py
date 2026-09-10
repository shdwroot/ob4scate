import pytest
from cryptography.fernet import Fernet

import tokenization_vault.main as vault


def test_vault_encryption_round_trip(monkeypatch):
    key = Fernet.generate_key()
    monkeypatch.setenv("VAULT_ENCRYPTION_KEY", key.decode())
    encrypted = vault._encryption().encrypt(b"sensitive value")
    assert encrypted != b"sensitive value"
    assert vault._encryption().decrypt(encrypted) == b"sensitive value"


def test_vault_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("VAULT_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="VAULT_ENCRYPTION_KEY is required"):
        vault._encryption()

    monkeypatch.setenv("VAULT_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(RuntimeError, match="not a valid Fernet key"):
        vault._encryption()

    monkeypatch.delenv("DB_PASS", raising=False)
    with pytest.raises(RuntimeError, match="DB_PASS is required"):
        vault.get_db_connection()
