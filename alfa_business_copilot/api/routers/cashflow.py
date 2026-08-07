from __future__ import annotations

import sqlite3

from catboost import CatBoostClassifier
from fastapi import APIRouter, Depends, HTTPException

from alfa_agent.cashflow import CashflowAgent, run_forecast, save_forecast

from api.deps import get_cashflow_agent, get_cashflow_conn, get_cashflow_model
from api.schemas.cashflow import CashflowDecisionOut, ClientOut, ExplainOut

router = APIRouter(prefix="/cashflow", tags=["cashflow"])


@router.get("/clients", response_model=list[ClientOut])
def list_clients(conn: sqlite3.Connection = Depends(get_cashflow_conn)) -> list[ClientOut]:
    rows = conn.execute("SELECT client_id, full_name FROM client").fetchall()
    return [ClientOut(client_id=r["client_id"], full_name=r["full_name"]) for r in rows]


def _get_client_account(conn: sqlite3.Connection, client_id: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    client = conn.execute("SELECT * FROM client WHERE client_id = ?", (client_id,)).fetchone()
    if client is None:
        raise HTTPException(404, f"Клиент {client_id!r} не найден")
    account = conn.execute("SELECT * FROM account WHERE client_id = ?", (client_id,)).fetchone()
    if account is None:
        raise HTTPException(404, f"Счёт клиента {client_id!r} не найден")
    return client, account


@router.get("/clients/{client_id}/decision", response_model=CashflowDecisionOut)
def get_decision(
    client_id: str,
    conn: sqlite3.Connection = Depends(get_cashflow_conn),
    model: CatBoostClassifier = Depends(get_cashflow_model),
    agent: CashflowAgent = Depends(get_cashflow_agent),
) -> CashflowDecisionOut:
    client, account = _get_client_account(conn, client_id)
    forecast = run_forecast(conn, model, account["account_id"])
    save_forecast(conn, account["account_id"], forecast)
    decision = agent.run(conn, account["account_id"], client["full_name"])
    return CashflowDecisionOut.model_validate(decision)


@router.post("/clients/{client_id}/explain", response_model=ExplainOut)
def explain(
    client_id: str,
    conn: sqlite3.Connection = Depends(get_cashflow_conn),
    model: CatBoostClassifier = Depends(get_cashflow_model),
    agent: CashflowAgent = Depends(get_cashflow_agent),
) -> ExplainOut:
    client, account = _get_client_account(conn, client_id)
    forecast = run_forecast(conn, model, account["account_id"])
    decision = agent.run(conn, account["account_id"], client["full_name"])
    if decision.gap_date is None or decision.gap_amount is None:
        raise HTTPException(409, "Разрыв не спрогнозирован — объяснять нечего")
    explanation = agent.explain_in_detail(
        client_name=client["full_name"],
        industry=client["industry"],
        balance=account["current_balance"],
        avg_daily_income=forecast["avg_daily_income_10d"],
        upcoming_expenses=forecast["upcoming_fixed_expenses_30d"],
        gap_date=decision.gap_date,
        gap_amount=decision.gap_amount,
        recommended_product=decision.recommended_product,
    )
    return ExplainOut(explanation=explanation)
