"""Encrypted token-to-value mapping service."""

import os
from contextlib import closing

import psycopg2
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from psycopg2.errors import UniqueViolation
from pydantic import BaseModel, Field

app = FastAPI(title="Tokenization Vault", version="0.2.0")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_USER = os.getenv("DB_USER", "vault_user")
DB_NAME = os.getenv("DB_NAME", "vault_db")


class StoreMappingRequest(BaseModel):
    original: str = Field(min_length=1, max_length=100_000)
    token: str = Field(min_length=8, max_length=512)
    synthetic: str = Field(min_length=1, max_length=100_000)


class RetrieveMappingRequest(BaseModel):
    token: str = Field(min_length=8, max_length=512)


def _encryption() -> Fernet:
    key = os.getenv("VAULT_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("VAULT_ENCRYPTION_KEY is required")
    try:
        return Fernet(key.encode())
    except (TypeError, ValueError) as exc:
        raise RuntimeError("VAULT_ENCRYPTION_KEY is not a valid Fernet key") from exc


def get_db_connection():
    password = os.getenv("DB_PASS")
    if not password:
        raise RuntimeError("DB_PASS is required")
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=password,
        dbname=DB_NAME,
        connect_timeout=5,
        application_name="ob4scate-tokenization-vault",
    )


def _database_is_ready() -> bool:
    with closing(get_db_connection()) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)


def _store_mapping(mapping: StoreMappingRequest) -> None:
    ciphertext = _encryption().encrypt(mapping.original.encode())
    with closing(get_db_connection()) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO token_mappings (original_ciphertext, token, synthetic)
                    VALUES (%s, %s, %s)
                    """,
                    (ciphertext, mapping.token, mapping.synthetic),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def _retrieve_mapping(token: str) -> tuple[bytes, str] | None:
    with closing(get_db_connection()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT original_ciphertext, synthetic
                FROM token_mappings
                WHERE token = %s
                """,
            (token,),
        )
        return cursor.fetchone()


@app.get("/health")
async def health_check() -> dict[str, str]:
    try:
        ready = await run_in_threadpool(_database_is_ready)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ok" if ready else "degraded"}


@app.post("/store", status_code=status.HTTP_201_CREATED)
async def store_mapping(mapping: StoreMappingRequest) -> dict[str, str]:
    try:
        await run_in_threadpool(_store_mapping, mapping)
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Token already exists"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vault is not configured",
        ) from exc
    return {"status": "stored"}


@app.post("/retrieve")
async def retrieve_mapping(data: RetrieveMappingRequest) -> dict[str, str]:
    try:
        row = await run_in_threadpool(_retrieve_mapping, data.token)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        original = _encryption().decrypt(bytes(row[0])).decode()
    except HTTPException:
        raise
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored mapping failed integrity validation",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vault is not configured",
        ) from exc
    return {"original": original, "synthetic": row[1]}
