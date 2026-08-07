from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from catboost import CatBoostClassifier

from alfa_agent.cashflow.forecasting import run_forecast
from alfa_agent.llm import LLMClient, get_client, render

MIN_CONFIDENCE_TO_ALERT = 0.4
MIN_GAP_AMOUNT_TO_ALERT = 1000
HIGH_SEVERITY_THRESHOLD = 10000
HIGH_SEVERITY_PRODUCT = "Овердрафт под прогноз выручки"


@dataclass(frozen=True)
class CashflowDecision:

    alert: bool
    reason: str | None = None
    severity: str | None = None
    message: str | None = None
    recommended_product: str | None = None
    gap_date: date | None = None
    gap_amount: float | None = None
    confidence_level: float | None = None


class CashflowAgent:

    def __init__(self, model: CatBoostClassifier, llm_client: LLMClient | None = None) -> None:
        self.model = model
        self.llm_client = llm_client or get_client()

    def run(self, conn: sqlite3.Connection, account_id: str, client_name: str) -> CashflowDecision:
        forecast = run_forecast(conn, self.model, account_id)
        gap_date = forecast["gap_date"]
        gap_amount = forecast["gap_amount"]
        confidence_level = forecast["confidence_level"]

        if gap_date is None:
            return CashflowDecision(alert=False, reason="разрыв не найден, всё в порядке")
        if confidence_level < MIN_CONFIDENCE_TO_ALERT:
            return CashflowDecision(alert=False, reason="уверенность прогноза слишком низкая")
        if abs(gap_amount) < MIN_GAP_AMOUNT_TO_ALERT:
            return CashflowDecision(alert=False, reason="сумма разрыва слишком маленькая")

        severity = "high" if abs(gap_amount) >= HIGH_SEVERITY_THRESHOLD else "medium"
        message = self._alert_message(gap_date, gap_amount, client_name, confidence_level, severity)

        return CashflowDecision(
            alert=True, severity=severity, message=message,
            recommended_product=HIGH_SEVERITY_PRODUCT if severity == "high" else None,
            gap_date=gap_date, gap_amount=gap_amount, confidence_level=confidence_level,
        )

    def explain_in_detail(
        self, client_name: str, industry: str, balance: float, avg_daily_income: float,
        upcoming_expenses: float, gap_date: date, gap_amount: float,
        recommended_product: str | None,
    ) -> str:
        system, user = render(
            "cashflow_explanation",
            client_name=client_name, industry=industry,
            balance=f"{balance:,.0f}".replace(",", " "),
            avg_daily_income=f"{avg_daily_income:,.0f}".replace(",", " "),
            upcoming_expenses=f"{upcoming_expenses:,.0f}".replace(",", " "),
            gap_date=gap_date.isoformat(),
            gap_amount=f"{abs(gap_amount):,.0f}".replace(",", " "),
            recommended_product=recommended_product or "нет",
        )
        return self.llm_client.generate(system=system, user=user)

    def _alert_message(
        self, gap_date: date, gap_amount: float, client_name: str,
        confidence_level: float, severity: str,
    ) -> str:
        system, user = render(
            "cashflow_alert",
            client_name=client_name,
            gap_date=gap_date.isoformat(),
            gap_amount=f"{abs(gap_amount):,.0f}".replace(",", " "),
            confidence=str(confidence_level),
            severity=severity,
        )
        return self.llm_client.generate(system=system, user=user)
