from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd

BALANCE_WINDOW_DAYS = 60
TOP_COUNTERPARTIES_LIMIT = 5


def balance_series(
    conn: sqlite3.Connection, account_id: str, window_days: int = BALANCE_WINDOW_DAYS
) -> list[dict]:
    """Восстанавливает баланс на конец каждого дня, где были операции, за
    последние window_days. account.current_balance — единственная точка
    правды на сегодня; идём от неё назад по реальным транзакциям (текущий
    минус будущие относительно каждой точки движения = баланс в этой точке).
    Точки только на датах с операциями, не на каждый календарный день —
    для линейного графика этого достаточно, между операциями баланс не
    менялся."""
    row = conn.execute(
        "SELECT current_balance FROM account WHERE account_id = ?", (account_id,)
    ).fetchone()
    if row is None:
        return []
    current_balance = row["current_balance"]

    df = pd.read_sql(
        "SELECT date, amount, direction FROM payment_transaction WHERE account_id = ?",
        conn, params=(account_id,),
    )
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y").dt.date
    df["signed"] = np.where(df["direction"] == "inbound", df["amount"], -df["amount"])
    daily_net = df.groupby("date")["signed"].sum().sort_index()

    balances: dict[date, float] = {}
    running = current_balance
    for d in reversed(daily_net.index.tolist()):
        balances[d] = running
        running -= daily_net[d]

    cutoff = date.today() - timedelta(days=window_days)
    return [
        {"date": d.isoformat(), "balance": round(balances[d], 2)}
        for d in sorted(balances) if d >= cutoff
    ]


def flow_summary(conn: sqlite3.Connection, account_id: str) -> dict:
    row = conn.execute(
        """SELECT
            SUM(CASE WHEN direction='inbound' THEN amount ELSE 0 END) AS inbound_total,
            SUM(CASE WHEN direction='outbound' THEN amount ELSE 0 END) AS outbound_total
        FROM payment_transaction WHERE account_id = ?""",
        (account_id,),
    ).fetchone()
    return {
        "inbound_total": round(row["inbound_total"] or 0, 2),
        "outbound_total": round(row["outbound_total"] or 0, 2),
    }


def top_counterparties(
    conn: sqlite3.Connection, account_id: str, limit: int = TOP_COUNTERPARTIES_LIMIT
) -> list[dict]:
    rows = conn.execute(
        """SELECT counterparty, SUM(amount) AS total
           FROM payment_transaction
           WHERE account_id = ? AND direction = 'outbound' AND counterparty IS NOT NULL
           GROUP BY counterparty
           ORDER BY total DESC
           LIMIT ?""",
        (account_id, limit),
    ).fetchall()
    return [{"counterparty": r["counterparty"], "amount": round(r["total"], 2)} for r in rows]
