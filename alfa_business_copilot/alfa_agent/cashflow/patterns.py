from __future__ import annotations

import sqlite3

import pandas as pd


def detect_recurring_patterns(conn: sqlite3.Connection) -> pd.DataFrame:
    df_out = pd.read_sql(
        "SELECT account_id, category_id, counterparty, date, amount "
        "FROM payment_transaction WHERE direction = 'outbound'",
        conn,
    )
    df_out["date"] = pd.to_datetime(df_out["date"], format="%d.%m.%Y")

    patterns = []
    for (account_id, category_id, counterparty), group in df_out.groupby(
        ["account_id", "category_id", "counterparty"]
    ):
        group = group.sort_values("date")
        if len(group) < 3:
            continue
        intervals = group["date"].diff().dt.days.dropna()
        amounts = group["amount"]
        interval_cv = intervals.std() / intervals.mean()
        amount_cv = amounts.std() / amounts.mean() if amounts.mean() else 1
        confidence = round(max(0.0, 1 - (interval_cv + amount_cv) / 2), 3)
        avg_interval = round(intervals.mean())
        avg_amount = round(amounts.mean(), 2)
        next_date = group["date"].max() + pd.Timedelta(days=avg_interval)

        patterns.append({
            "account_id": account_id, "category_id": category_id, "counterparty": counterparty,
            "expected_amount": avg_amount, "frequency_days": avg_interval,
            "next_expected_date": next_date.strftime("%Y-%m-%d"), "confidence_score": confidence,
        })

    return pd.DataFrame(patterns)


def save_patterns(conn: sqlite3.Connection, patterns_df: pd.DataFrame) -> None:
    conn.execute("DELETE FROM recurring_pattern")
    conn.commit()
    if patterns_df.empty:
        return
    patterns_df.to_sql("recurring_pattern", conn, if_exists="append", index=False)


def refresh_recurring_patterns(conn: sqlite3.Connection) -> pd.DataFrame:
    patterns_df = detect_recurring_patterns(conn)
    save_patterns(conn, patterns_df)
    return patterns_df
