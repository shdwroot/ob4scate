from fastapi import FastAPI
import psycopg2
import os

app = FastAPI(title="Tokenization Vault", version="0.1.0")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "vault_user")
DB_PASS = os.getenv("DB_PASS", "vault_pass")
DB_NAME = os.getenv("DB_NAME", "vault_db")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/store")
async def store_mapping(mapping: dict):
    """
    Store original ↔ token ↔ synthetic mapping.
    """
    original = mapping.get("original")
    token = mapping.get("token")
    synthetic = mapping.get("synthetic")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO token_mappings (original, token, synthetic) VALUES (%s, %s, %s)",
        (original, token, synthetic)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"status": "stored"}


@app.post("/retrieve")
async def retrieve_mapping(data: dict):
    """
    Retrieve mapping based on token.
    """
    token = data.get("token")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT original, synthetic FROM token_mappings WHERE token = %s",
        (token,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return {"original": row[0], "synthetic": row[1]}
    return {"error": "Token not found"}