"""Прогоняет 5 сценариев демо-презентации через реальный API (живой LLM) и
записывает все LLM-вызовы в demo_fixtures.json. Требует настоящего ключа в
.env и выключенного DEMO_MODE — иначе просто нечего было бы записывать.

Все сценарии, где это применимо, — от лица Алины Гарифуллиной (студия
маникюра, сквозной демо-клиент). Кассовый разрыв не включён: у Алины он не
конструировался (alert=False), а LLM там дёргается только внутри алерта.

Запуск: ./.venv/Scripts/python.exe scripts/record_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from httpx import Response

from api.demo import RecordingLLMClient, fixtures_path, is_demo_mode, save_fixtures
from api.main import app


def _must_ok(response: Response) -> dict:
    if response.status_code != 200:
        raise SystemExit(
            f"{response.request.method} {response.request.url} -> "
            f"{response.status_code}: {response.text}"
        )
    return response.json()


def main() -> None:
    if is_demo_mode():
        raise SystemExit(
            "DEMO_MODE включён — запись фикстур требует живого ключа и настоящего "
            "LLMClient. Уберите DEMO_MODE из окружения/.env и запустите снова."
        )

    with TestClient(app) as client:
        # RecordingLLMClient оборачивает уже собранный при старте LazyLLMClient
        # (тот же самый на все 4 агента) — резолвится в настоящий DeepSeek/OpenRouter
        # клиент по env из .env при первом реальном вызове.
        recorder = RecordingLLMClient(app.state.acquisition_agent.llm_client)
        for attr in ("acquisition_agent", "cashflow_agent", "gov_agent", "insurance_agent"):
            getattr(app.state, attr).llm_client = recorder

        # --- 1. Привлечение: студия маникюра в Казани + follow-up про бюджет ---
        recorder.scenario = "acquisition_manicure_kazan_turn1"
        r1 = _must_ok(client.post(
            "/acquisition/messages",
            json={"message": "хочу открыть студию маникюра в Казани"},
        ))
        session_id = r1["session_id"]
        print(f"[1] turn1 reply: {r1['reply'][:120]}...")

        recorder.scenario = "acquisition_manicure_kazan_turn2_budget"
        r2 = _must_ok(client.post(
            "/acquisition/messages",
            json={"session_id": session_id, "message": "у меня бюджет около 700 тысяч рублей"},
        ))
        print(f"[1] turn2 reply: {r2['reply'][:120]}...")

        # --- 2. Гос поддержка: Алина, социальный контракт ---
        beauty_client_id = app.state.gov_beauty_client_id
        programs = _must_ok(client.get(f"/gov_support/programs?client_id={beauty_client_id}"))
        target = next(
            (p for p in programs["eligible"] if "социальный контракт" in p["program_name"].lower()),
            None,
        )
        if target is None:
            raise SystemExit(
                "Программа 'Социальный контракт' не найдена среди подходящих Алине "
                "программ — проверьте industry_allowed в normalize.py и "
                "otbor/mery-podderzhki-msp-2026.csv. Фикстуры не записаны."
            )
        recorder.scenario = "gov_support_alina_social_contract_advice"
        advice = _must_ok(client.get(
            f"/gov_support/programs/{target['program_id']}/advice?client_id={beauty_client_id}"
        ))
        print(f"[2] advice: {advice['explanation'][:120]}...")

        # --- 3. Страхование: рекомендация Алине + follow-up про второй продукт ---
        recorder.scenario = "insurance_recommendation_demo_beauty"
        rec = _must_ok(client.get("/insurance/clients/demo_beauty/recommendation"))
        if rec["reply"] is None:
            raise SystemExit(
                "У demo_beauty нет рекомендаций — проверьте "
                "alfa_agent/insurance/fixtures.py::demo_beauty_client_features. "
                "Фикстуры не записаны."
            )
        print(f"[3] recommendation: {rec['reply'][:120]}...")

        recorder.scenario = "insurance_followup_second_product"
        followup = _must_ok(client.post(
            f"/insurance/sessions/{rec['session_id']}/followup",
            json={"message": "а что насчёт второго продукта в списке, чем он отличается?"},
        ))
        print(f"[3] followup: {followup['reply'][:120]}...")

    save_fixtures(fixtures_path(), recorder.entries)
    print(f"\nЗаписано {len(recorder.entries)} фикстур -> {fixtures_path()}")


if __name__ == "__main__":
    main()
