from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from alfa_agent.cashflow.db import PROJECT_ROOT

TRANSACTIONS_CSV_PATH = PROJECT_ROOT / "otbor" / "alfa.csv"


def _shift_dates_to_present(df: pd.DataFrame) -> pd.DataFrame:
    """alfa.csv — статичный снимок; его даты со временем уезжают в прошлое
    относительно date.today(), из-за чего next_expected_date в
    recurring_pattern протухает и прогноз перестаёт видеть повторяющиеся
    списания вообще (см. seed_demo_alert_client — та же проблема, там просто
    обошли её, сгенерировав данные заново). Здесь вместо этого сдвигаем все
    даты CSV на одинаковое число дней, чтобы последняя транзакция приходилась
    на вчера, — интервалы между транзакциями не меняются, меняется только
    точка отсчёта, так что регулярные платежи, которые находит patterns.py,
    остаются теми же самыми по структуре."""
    parsed = pd.to_datetime(df["date"], format="%d.%m.%Y")
    shift = (date.today() - timedelta(days=1)) - parsed.max().date()
    df = df.copy()
    df["date"] = (parsed + shift).dt.strftime("%d.%m.%Y")
    return df


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
    df = _shift_dates_to_present(df)
    df.to_sql("payment_transaction", conn, if_exists="append", index=False)
    return len(df)
