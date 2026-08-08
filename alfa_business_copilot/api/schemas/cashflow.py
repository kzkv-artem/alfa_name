from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class ClientOut(BaseModel):
    client_id: str
    full_name: str


class CashflowDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert: bool
    reason: str | None = None
    severity: str | None = None
    message: str | None = None
    recommended_product: str | None = None
    gap_date: date | None = None
    gap_amount: float | None = None
    confidence_level: float | None = None
    history_depth_days: int | None = None
    alert_threshold: float


class ExplainOut(BaseModel):
    explanation: str
