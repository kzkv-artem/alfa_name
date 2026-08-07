from __future__ import annotations

import sqlite3
from typing import Iterator

from catboost import CatBoostClassifier
from fastapi import Request

from alfa_agent.acquisition import RiskAdvisorAgent
from alfa_agent.cashflow import CashflowAgent
from alfa_agent.gov_support import GovSupportAgent
from alfa_agent.insurance import ClientFeatures, InsuranceAdvisorAgent
from alfa_agent.llm import LLMClient, get_client


class LazyLLMClient(LLMClient):
    """Defers real LLM client construction (and its config validation) to the
    first actual call. Lets the API start with no DEEPSEEK_API_KEY configured —
    only requests that reach the LLM fail, not the whole process."""

    def __init__(self) -> None:
        self._real: LLMClient | None = None

    def _resolve(self) -> LLMClient:
        if self._real is None:
            self._real = get_client()
        return self._real

    def generate(self, *args, **kwargs) -> str:
        return self._resolve().generate(*args, **kwargs)

    def generate_json(self, *args, **kwargs) -> dict:
        return self._resolve().generate_json(*args, **kwargs)


def get_cashflow_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(request.app.state.cashflow_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_gov_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(request.app.state.gov_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_cashflow_model(request: Request) -> CatBoostClassifier:
    return request.app.state.cashflow_model


def get_acquisition_agent(request: Request) -> RiskAdvisorAgent:
    return request.app.state.acquisition_agent


def get_cashflow_agent(request: Request) -> CashflowAgent:
    return request.app.state.cashflow_agent


def get_gov_agent(request: Request) -> GovSupportAgent:
    return request.app.state.gov_agent


def get_insurance_agent(request: Request) -> InsuranceAdvisorAgent:
    return request.app.state.insurance_agent


def get_gov_demo_client_id(request: Request) -> int:
    return request.app.state.gov_demo_client_id


def get_insurance_features_index(request: Request) -> dict[str, ClientFeatures]:
    return request.app.state.insurance_features
