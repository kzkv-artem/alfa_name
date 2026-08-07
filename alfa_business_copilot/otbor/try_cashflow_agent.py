from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alfa_agent.cashflow import (
    CashflowAgent,
    connect,
    load_model,
    refresh_recurring_patterns,
    save_forecast,
    train_model,
)
from alfa_agent.cashflow.fixtures import seed_demo_client
from alfa_agent.cashflow.forecasting import run_forecast
from alfa_agent.cashflow.ingest import load_transactions_csv
from alfa_agent.cashflow.model import MODEL_PATH, save_model
from alfa_agent.llm import LLMError


def main() -> None:
    conn = connect()
    seed_demo_client(conn)
    n_tx = load_transactions_csv(conn)
    print(f"Транзакций загружено: {n_tx}")

    patterns_df = refresh_recurring_patterns(conn)
    print(f"Регулярных платежей найдено: {len(patterns_df)}")

    if not MODEL_PATH.exists():
        print("Модель не найдена, обучаю...")
        model, metrics = train_model()
        save_model(model)
        print(f"Готово. Accuracy: {metrics['accuracy']}   ROC-AUC: {metrics['roc_auc']}")
    else:
        model = load_model()

    agent = CashflowAgent(model)

    clients = conn.execute("SELECT client_id, full_name FROM client").fetchall()
    for c in clients:
        account = conn.execute(
            "SELECT account_id FROM account WHERE client_id = ?", (c["client_id"],)
        ).fetchone()

        forecast = run_forecast(conn, model, account["account_id"])
        save_forecast(conn, account["account_id"], forecast)

        print(f"\n=== {c['full_name']} ===")
        try:
            decision = agent.run(conn, account["account_id"], c["full_name"])
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")
            continue

        if not decision.alert:
            print(f"Разрыв не грозит: {decision.reason}")
            continue

        print(f"Уверенность: {decision.confidence_level}   Серьёзность: {decision.severity}")
        print(decision.message)
        if decision.recommended_product:
            print(f"Рекомендуемый продукт: {decision.recommended_product}")


if __name__ == "__main__":
    main()
