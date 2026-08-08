from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from alfa_agent.acquisition import RiskAdvisorAgent
from alfa_agent.cashflow import DB_PATH as CASHFLOW_DB_PATH
from alfa_agent.cashflow import CashflowAgent
from alfa_agent.cashflow import connect as cashflow_connect
from alfa_agent.cashflow import load_model, refresh_recurring_patterns, train_model
from alfa_agent.cashflow.fixtures import (
    seed_demo_alert_client,
    seed_demo_beauty_client as seed_demo_beauty_cashflow_client,
    seed_demo_client,
)
from alfa_agent.cashflow.ingest import load_transactions_csv
from alfa_agent.cashflow.model import MODEL_PATH, save_model
from alfa_agent.gov_support import DB_PATH as GOV_DB_PATH
from alfa_agent.gov_support import GovSupportAgent, build_database, normalize_programs
from alfa_agent.gov_support.fixtures import (
    seed_demo_beauty_client as seed_demo_beauty_gov_client,
    seed_demo_data,
)
from alfa_agent.gov_support.ingest import load_raw_programs
from alfa_agent.insurance import InsuranceAdvisorAgent
from alfa_agent.insurance import synthetic as insurance_synthetic
from alfa_agent.insurance.fixtures import demo_beauty_client_features
from alfa_agent.llm import LLMClient

from api.demo import is_demo_mode
from api.deps import build_llm_client
from api.errors import register_error_handlers
from api.routers import acquisition, cashflow, gov_support, insurance


def _init_cashflow(llm_client: LLMClient) -> tuple[Path, object, CashflowAgent]:
    # Идемпотентно: CREATE TABLE IF NOT EXISTS, безопасно вызывать при каждом старте.
    conn = cashflow_connect()
    seed_demo_client(conn)
    load_transactions_csv(conn)  # полная перезагрузка транзакций — только на старте!
    seed_demo_alert_client(conn)  # второй демо-клиент, специально с разрывом (даты от today())
    seed_demo_beauty_cashflow_client(conn)  # третий — студия маникюра, сквозной по всем линиям
    refresh_recurring_patterns(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()

    if MODEL_PATH.exists():
        model = load_model()
    else:
        model, _metrics = train_model()
        save_model(model)

    agent = CashflowAgent(model, llm_client=llm_client)
    return CASHFLOW_DB_PATH, model, agent


def _init_gov_support(llm_client: LLMClient) -> tuple[Path, int, int, GovSupportAgent]:
    # build_database() дропает и пересоздаёт файл БД — вызывать ровно один раз здесь,
    # никогда per-request, иначе каждый запрос будет стирать eligibility_check/documents.
    conn = build_database()
    load_raw_programs(conn)
    normalize_programs(conn)
    client_id, doc_type_ids = seed_demo_data(conn)
    beauty_client_id = seed_demo_beauty_gov_client(conn, doc_type_ids)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()

    agent = GovSupportAgent(llm_client=llm_client)
    return GOV_DB_PATH, client_id, beauty_client_id, agent


def _init_insurance(llm_client: LLMClient) -> tuple[dict, InsuranceAdvisorAgent]:
    if not insurance_synthetic.FEATURES_CSV_PATH.exists():
        features, labels = insurance_synthetic.generate()
        insurance_synthetic.save_features_csv(features)
        insurance_synthetic.save_labels_csv(labels)
    features = insurance_synthetic.load_features_csv()
    index = {f.client_id: f for f in features}
    demo_beauty = demo_beauty_client_features()
    index[demo_beauty.client_id] = demo_beauty  # сквозной клиент, тот же, что в cashflow/gov_support

    agent = InsuranceAdvisorAgent(llm_client=llm_client)
    return index, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm_client = build_llm_client()

    app.state.acquisition_agent = RiskAdvisorAgent(llm_client=llm_client)

    cashflow_db_path, model, cashflow_agent = _init_cashflow(llm_client)
    app.state.cashflow_db_path = cashflow_db_path
    app.state.cashflow_model = model
    app.state.cashflow_agent = cashflow_agent

    gov_db_path, gov_demo_client_id, gov_beauty_client_id, gov_agent = _init_gov_support(llm_client)
    app.state.gov_db_path = gov_db_path
    app.state.gov_demo_client_id = gov_demo_client_id
    app.state.gov_beauty_client_id = gov_beauty_client_id
    app.state.gov_agent = gov_agent

    insurance_features, insurance_agent = _init_insurance(llm_client)
    app.state.insurance_features = insurance_features
    app.state.insurance_agent = insurance_agent

    yield


app = FastAPI(title="Alfa Business Copilot API", lifespan=lifespan)
register_error_handlers(app)

app.include_router(acquisition.router)
app.include_router(cashflow.router)
app.include_router(gov_support.router)
app.include_router(insurance.router)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "demo_mode": is_demo_mode()}


# Монтировать статику нужно строго последней строкой: Mount("/") — это
# catch-all по префиксу, и Starlette отдаёт запрос первому совпавшему
# маршруту в порядке регистрации. Помести это выше — и оно перехватит вообще
# все запросы (включая роутеры и /health) раньше, чем до них дойдёт очередь.
app.mount("/", StaticFiles(directory=str(PROJECT_ROOT / "static"), html=True), name="static")
