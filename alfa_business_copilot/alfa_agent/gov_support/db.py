from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "otbor" / "gospodderzhka.db"
SCHEMA_PATH = PROJECT_ROOT / "otbor" / "schema.sql"


def build_database(db_path: Path = DB_PATH, schema_path: Path = SCHEMA_PATH) -> sqlite3.Connection:
    db_path.unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.row_factory = sqlite3.Row
    return conn
