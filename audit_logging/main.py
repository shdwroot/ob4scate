from fastapi import FastAPI
from pydantic import BaseModel
import datetime
import sqlite3
import os
import logging
import sys

app = FastAPI(title="Audit Logging Service", version="0.4.3")

DB_PATH = os.getenv("AUDIT_LOG_DB", "audit_logs.db")

# Ensure logs directory inside project root
PROJECT_ROOT = os.path.abspath(os.getcwd())
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOGS_DIR, "audit_service.log")

# Force create logs directory
os.makedirs(LOGS_DIR, exist_ok=True)

# Force create log file
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== Audit Logging Service Started ===\n")

# Configure logging
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
stream_handler = logging.StreamHandler(sys.stdout)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[file_handler, stream_handler]
)

logging.info(f"Logging initialized. Host log file path: {LOG_FILE}")

# Ensure DB exists
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    event_type TEXT,
    event_data TEXT
)
""")
conn.commit()
conn.close()
logging.info("Database initialized.")

class AuditLog(BaseModel):
    event_type: str
    event_data: dict

@app.get("/health")
async def health_check():
    logging.debug("Health check accessed.")
    file_handler.flush()
    return {"status": "ok", "log_file": LOG_FILE}

@app.post("/log")
async def log_event(event: AuditLog):
    timestamp = datetime.datetime.utcnow().isoformat()
    log_msg = f"Logging event - Type: {event.event_type}, Data: {event.event_data}"
    logging.info(log_msg)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO audit_logs (timestamp, event_type, event_data) VALUES (?, ?, ?)",
        (timestamp, event.event_type, str(event.event_data))
    )
    conn.commit()
    conn.close()

    logging.debug(f"Event stored at {timestamp}")
    file_handler.flush()
    return {"status": "logged", "log_file": LOG_FILE}

@app.get("/logs")
async def get_logs(limit: int = 100):
    logging.debug(f"Retrieving last {limit} logs.")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, event_type, event_data FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    logging.debug(f"Fetched {len(rows)} records.")
    file_handler.flush()
    return [
        {"id": r[0], "timestamp": r[1], "event_type": r[2], "event_data": r[3]}
        for r in rows
    ]