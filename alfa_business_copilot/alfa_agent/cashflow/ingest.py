from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from alfa_agent.cashflow.db import PROJECT_ROOT

TRANSACTIONS_CSV_PATH = PROJECT_ROOT / "otbor" / "alfa.csv"


def load_transactions_csv(conn: sqlite3.Connection, path: Path = TRANSACTIONS_CSV_PATH) -> int:
    conn.execute("DELETE FROM payment_transaction")
    conn.commit()

    df = None
    for sep in [",", ";"]:
        for encoding in ["utf-8", "utf-8-sig", "cp1251", "mac_cyrillic"]:
            try:
                df = pd.read_csv(path, sep=sep, encoding=encoding)
                if "transaction_id" in df.columns:
                    break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        if df is not None and "transaction_id" in df.columns:
            break

    if df is None or "transaction_id" not in df.columns:
        raise ValueError(f"Не удалось разобрать {path}: не найдена колонка transaction_id")

    df = df.drop_duplicates(subset="transaction_id", keep="first")
    df.to_sql("payment_transaction", conn, if_exists="append", index=False)
    return len(df)
