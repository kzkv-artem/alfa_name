from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "otbor" / "cashflow_v2.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS client (
    client_id           TEXT PRIMARY KEY,
    full_name           TEXT NOT NULL,
    birth_date          TEXT NOT NULL,
    industry             TEXT NOT NULL,
    registration_date       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account (
    account_id        TEXT PRIMARY KEY,
    client_id         TEXT NOT NULL REFERENCES client(client_id),
    opening_date          TEXT NOT NULL,
    current_balance   NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payment_transaction (
    transaction_id   TEXT PRIMARY KEY,
    account_id       TEXT NOT NULL REFERENCES account(account_id),
    category_id      INTEGER,
    date              TEXT NOT NULL,
    amount             NUMERIC NOT NULL,
    direction           TEXT NOT NULL,
    counterparty          TEXT,
    payment_method          TEXT
);

CREATE TABLE IF NOT EXISTS recurring_pattern (
    account_id TEXT, category_id INTEGER, counterparty TEXT, expected_amount NUMERIC,
    frequency_days INTEGER, next_expected_date TEXT, confidence_score NUMERIC
);

CREATE TABLE IF NOT EXISTS forecast (
    account_id             TEXT,
    generated_at              TEXT,
    predicted_gap_date           TEXT,
    predicted_gap_amount            NUMERIC,
    confidence_level                   NUMERIC
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
