CREATE TABLE IF NOT EXISTS token_mappings (
    id BIGSERIAL PRIMARY KEY,
    original_ciphertext BYTEA NOT NULL,
    token TEXT NOT NULL UNIQUE,
    synthetic TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_token_mappings_created_at
    ON token_mappings (created_at);
