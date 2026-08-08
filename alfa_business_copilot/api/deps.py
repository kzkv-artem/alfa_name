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

from api.demo import CachingLLMClient, DemoLLMClient, is_cache_enabled, is_demo_mode


def build_llm_client() -> LLMClient:
    """Что именно подставляется агентам в качестве LLMClient. DEMO_MODE и
    LLM_CACHE взаимоисключающи по смыслу: в DEMO_MODE живых вызовов нет
    вообще, кэшировать нечего."""
    if is_demo_mode():
        return DemoLLMClient()
    client: LLMClient = LazyLLMClient()
    if is_cache_enabled():
        client = CachingLLMClient(client)
    return client


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
    # check_same_thread=False: FastAPI выполняет pre-yield часть этой
    # generator-зависимости (contextmanager_in_threadpool) и тело хендлера
    # (run_endpoint_function) каждое своим отдельным run_in_threadpool —
    # это НЕ гарантированно один и тот же поток threadpool'а anyio, даже в
    # рамках одного запроса. Соединение по-прежнему одно на запрос, не
    # шарится между запросами — просто ему нельзя запрещать смену потока
    # внутри жизни одного запроса.
    conn = sqlite3.connect(request.app.state.cashflow_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_gov_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(request.app.state.gov_db_path, check_same_thread=False)
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


def get_gov_client_id(request: Request, client_id: int | None = None) -> int:
    """client_id — query-параметр эндпоинтов /gov_support/...; если не передан,
    используется исходный демо-клиент из app.state (тот же дефолт, что был
    раньше жёстко зашит в get_gov_demo_client_id)."""
    return client_id if client_id is not None else request.app.state.gov_demo_client_id


def get_insurance_features_index(request: Request) -> dict[str, ClientFeatures]:
    return request.app.state.insurance_features
