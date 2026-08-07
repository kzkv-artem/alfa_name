from __future__ import annotations

import select
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alfa_agent.llm import LLMError

IDLE_TIMEOUT_SECONDS = 360
GOODBYE_MESSAGE = "Спасибо за ваше обращение! Будем ждать вас снова!"


class IdleTimeout(Exception):
    pass


def _prompt(text: str) -> str:
    print(text, end="", flush=True)
    try:
        ready, _, _ = select.select([sys.stdin], [], [], IDLE_TIMEOUT_SECONDS)
    except (OSError, ValueError):
        ready = [sys.stdin]
    if not ready:
        raise IdleTimeout
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n")


def run_acquisition() -> None:
    from alfa_agent.acquisition import RiskAdvisorAgent, RiskChatState

    agent = RiskAdvisorAgent()
    state = RiskChatState()
    print("Опишите бизнес, который хотите открыть — например: «хочу открыть кофейню, риски?»")
    print("Для выхода наберите «выход».\n")

    while True:
        try:
            user_message = _prompt("Вы: ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not user_message:
            continue
        if user_message.lower() in ("выход", "exit", "quit"):
            return

        try:
            reply, state = agent.handle_message(user_message, state)
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")
            continue
        print(f"Штурман: {reply}\n")


def run_cashflow() -> None:
    from alfa_agent.cashflow import CashflowAgent, connect, load_model, refresh_recurring_patterns, save_forecast, train_model
    from alfa_agent.cashflow.fixtures import seed_demo_client
    from alfa_agent.cashflow.forecasting import run_forecast
    from alfa_agent.cashflow.ingest import load_transactions_csv
    from alfa_agent.cashflow.model import MODEL_PATH, save_model

    conn = connect()
    seed_demo_client(conn)
    load_transactions_csv(conn)
    refresh_recurring_patterns(conn)

    if not MODEL_PATH.exists():
        print("Модель ещё не обучена, обучаю...")
        model, _ = train_model()
        save_model(model)
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

        print(decision.message)
        if decision.recommended_product:
            print(f"Рекомендуемый продукт: {decision.recommended_product}")


def run_gov_support() -> None:
    from alfa_agent.gov_support import GovSupportAgent, build_database, run_matching
    from alfa_agent.gov_support.fixtures import seed_demo_data
    from alfa_agent.gov_support.ingest import load_raw_programs
    from alfa_agent.gov_support.normalize import normalize_programs

    conn = build_database()
    load_raw_programs(conn)
    normalize_programs(conn)
    client_id, _ = seed_demo_data(conn)

    as_of = date.today().isoformat()
    results = run_matching(conn, client_id, as_of)
    client = conn.execute("SELECT * FROM client WHERE client_id=?", (client_id,)).fetchone()

    eligible = [r for r in results if r["is_eligible"]]
    print(f"Подходит программ: {len(eligible)} из {len(results)}")
    if not eligible:
        print("Ни одна программа сейчас не подходит.")
        return

    for i, r in enumerate(eligible, 1):
        print(f"  {i}. {r['program']['name']}")

    choice = _prompt("Номер программы для подробностей (Enter — пропустить): ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(eligible)):
        return

    r = eligible[int(choice) - 1]
    program = r["program"]
    agent = GovSupportAgent()

    try:
        advice = agent.advise(conn, client, program, r["is_eligible"], r["reason"])
    except LLMError as exc:
        print(f"[Ошибка LLM] {exc}")
        return

    print(f"\n{advice.explanation}")
    try:
        if advice.decision == "propose_draft":
            print("--- черновик заявления ---")
            print(agent.draft_application(client, program, list(advice.missing_documents)))
        elif advice.decision == "request_documents":
            print("--- запрос документов ---")
            print(agent.request_documents(conn, client, program))
    except LLMError as exc:
        print(f"[Ошибка LLM] {exc}")


def run_insurance() -> None:
    from alfa_agent.insurance import InsuranceAdvisorAgent
    from alfa_agent.insurance import synthetic as insurance_synthetic

    if not insurance_synthetic.FEATURES_CSV_PATH.exists():
        print("Синтетических клиентов ещё нет, генерирую...")
        features, labels = insurance_synthetic.generate()
        insurance_synthetic.save_features_csv(features)
        insurance_synthetic.save_labels_csv(labels)

    features = insurance_synthetic.load_features_csv()
    candidates = [f for f in features if f.legal_form != "самозанятый"]
    target = candidates[0]
    print(f"Демо-клиент: {target.client_id}, {target.legal_form}, ОКВЭД {target.okved}")

    agent = InsuranceAdvisorAgent()
    try:
        reply, assessment = agent.recommend_and_explain(target)
    except LLMError as exc:
        print(f"[Ошибка LLM] {exc}")
        return

    if reply is None:
        print("Подходящих продуктов сейчас нет — это нормальный результат, агент промолчал.")
        return
    print(reply)

    print("\nСсылки на оформление:")
    for rec in assessment.recommendations:
        print(f"  {rec.product.client_name}: {rec.product.link}")

    print("\nМожете задать уточняющий вопрос про эти продукты (пусто — выход).")
    while True:
        try:
            question = _prompt("Вы: ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not question:
            return
        try:
            answer = agent.answer_followup(question, assessment)
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")
            continue
        print(f"Штурман: {answer}\n")


PRODUCT_MENU = {
    "1": ("Кассовый разрыв", run_cashflow),
    "2": ("Гос поддержка", run_gov_support),
    "3": ("Страхование", run_insurance),
}


def run_product_line() -> None:
    while True:
        print("Линия «Продукт» — выберите раздел:")
        for key, (label, _) in PRODUCT_MENU.items():
            print(f"  {key}. {label}")
        print("  0. Назад")

        try:
            choice = _prompt("> ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if choice == "0":
            return

        entry = PRODUCT_MENU.get(choice)
        if not entry:
            print("Нет такого пункта.\n")
            continue

        print()
        entry[1]()
        print()


MAIN_MENU = {
    "1": ("Привлечение — риски открытия бизнеса", run_acquisition),
    "2": ("Продукт — кассовый разрыв, гос поддержка, страхование", run_product_line),
}


def main() -> None:
    print("Alfa Business Copilot\n")
    try:
        while True:
            print("Выберите линию:")
            for key, (label, _) in MAIN_MENU.items():
                print(f"  {key}. {label}")
            print("  0. Выход")

            try:
                choice = _prompt("> ").strip()
            except (KeyboardInterrupt, EOFError):
                return
            if choice == "0":
                return

            entry = MAIN_MENU.get(choice)
            if not entry:
                print("Нет такого пункта.\n")
                continue

            print()
            entry[1]()
            print()
    except IdleTimeout:
        print(f"\n{GOODBYE_MESSAGE}")


if __name__ == "__main__":
    main()
