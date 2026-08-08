from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd
from catboost import CatBoostClassifier

from alfa_agent.cashflow.model import FEATURE_COLUMNS

FORECAST_HORIZON_DAYS = 21
INCOME_LOOKBACK_DAYS = 12


def run_forecast(conn: sqlite3.Connection, model: CatBoostClassifier, account_id: str) -> dict:
    row = conn.execute(
        """SELECT a.current_balance, a.opening_date, c.industry, c.registration_date
           FROM account a JOIN client c ON c.client_id = a.client_id
           WHERE a.account_id = ?""", (account_id,)
    ).fetchone()

    balance = row["current_balance"]
    industry = row["industry"]
    today = date.today()
    reg_date = date.fromisoformat(row["registration_date"])
    business_age_months = (today.year - reg_date.year) * 12 + (today.month - reg_date.month)
    account_age_days = (today - date.fromisoformat(row["opening_date"])).days

    # date хранится текстом как ДД.ММ.ГГГГ — сравнивать его со строкой вида
    # today.isoformat() ("ГГГГ-ММ-ДД") прямо в SQL нельзя: это два разных
    # текстовых формата, и `>=` в SQLite сравнивает их лексикографически, а не
    # как даты. Тянем все inbound-транзакции без фильтра, приводим date к
    # datetime тем же форматом, что уже использует patterns.py, и фильтруем
    # окна здесь — сравнивая настоящие даты, а не их текстовые представления.
    df_inbound = pd.read_sql(
        "SELECT date, amount FROM payment_transaction WHERE account_id=? AND direction='inbound'",
        conn, params=(account_id,))
    df_inbound["date"] = pd.to_datetime(df_inbound["date"], format="%d.%m.%Y")

    since_30 = pd.Timestamp(today - timedelta(days=30))
    since_10 = pd.Timestamp(today - timedelta(days=INCOME_LOOKBACK_DAYS))
    df_30 = df_inbound[df_inbound["date"] >= since_30]
    df_10 = df_inbound[df_inbound["date"] >= since_10]

    avg_income_30 = df_30.groupby("date")["amount"].sum().mean() if not df_30.empty else 0
    avg_income_10 = df_10.groupby("date")["amount"].sum().mean() if not df_10.empty else 0
    volatility = (df_10.groupby("date")["amount"].sum().std() / avg_income_10) if avg_income_10 else 0

    patterns_list = pd.read_sql(
        "SELECT * FROM recurring_pattern WHERE account_id = ?", conn, params=(account_id,)
    ).to_dict("records")

    running_balance = balance
    gap_date, gap_amount = None, None
    for i in range(1, FORECAST_HORIZON_DAYS + 1):
        day = today + timedelta(days=i)
        running_balance += avg_income_10
        for p in patterns_list:
            if date.fromisoformat(p["next_expected_date"]) == day:
                running_balance -= p["expected_amount"]
        if running_balance < 0 and gap_date is None:
            gap_date, gap_amount = day, round(running_balance, 2)

    features_row = pd.DataFrame([{
        "avg_daily_income_30d": avg_income_30,
        "avg_daily_income_10d": avg_income_10,
        "income_volatility": volatility,
        "income_trend": (avg_income_10 / avg_income_30) if avg_income_30 else 1.0,
        "current_balance": balance,
        "upcoming_fixed_expenses_30d": sum(p["expected_amount"] for p in patterns_list),
        "n_recurring_patterns": len(patterns_list),
        "avg_pattern_confidence": (
            sum(p["confidence_score"] for p in patterns_list) / len(patterns_list)
            if patterns_list else 0.0
        ),
        "business_age_months": business_age_months,
        "account_age_days": account_age_days,
        "industry": industry,
    }])[FEATURE_COLUMNS]
    confidence_level = round(float(model.predict_proba(features_row)[0, 1]), 3)

    return {
        "gap_date": gap_date, "gap_amount": gap_amount, "confidence_level": confidence_level,
        "avg_daily_income_10d": avg_income_10,
        "upcoming_fixed_expenses_30d": sum(p["expected_amount"] for p in patterns_list),
    }


def save_forecast(conn: sqlite3.Connection, account_id: str, forecast: dict) -> None:
    if forecast["gap_date"] is None:
        return
    conn.execute("DELETE FROM forecast WHERE account_id = ?", (account_id,))
    conn.execute(
        "INSERT INTO forecast VALUES (?, datetime('now'), ?, ?, ?)",
        (account_id, forecast["gap_date"].isoformat(), forecast["gap_amount"], forecast["confidence_level"]),
    )
    conn.commit()
