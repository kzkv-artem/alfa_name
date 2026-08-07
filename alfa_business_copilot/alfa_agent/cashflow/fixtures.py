from __future__ import annotations

import sqlite3


def seed_demo_client(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO client VALUES (?, ?, ?, ?, ?)",
        ("client_1", "Дарья Соколова", "2002-04-12", "HoReCa", "2026-03-15"),
    )
    conn.execute(
        "INSERT OR REPLACE INTO account VALUES (?, ?, ?, ?)",
        ("account_1", "client_1", "2026-03-15", 18000),
    )
    conn.commit()
