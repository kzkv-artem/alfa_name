from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("[i] python-dotenv не установлен — читаю переменные прямо из окружения")

from alfa_agent.llm import (
    LLMConfig,
    LLMError,
    get_client,
    list_templates,
    render,
)


def check_config() -> LLMConfig:
    print("\n=== 1. Конфигурация ===")
    config = LLMConfig.from_env()
    print(config.describe())
    if not config.api_key:
        print(f"\n[X] Ключ не найден. Заполните {config.key_env_var} в файле .env")
        sys.exit(1)
    print("[v] Конфиг собран")
    return config


def check_prompts() -> None:
    print("\n=== 2. Шаблоны промптов ===")
    samples = {
        "cashflow_alert": dict(
            client_name="Дарья",
            gap_date="2026-08-19",
            gap_amount="-12 400",
            confidence="0.72",
            severity="high",
        ),
        "cashflow_explanation": dict(
            client_name="Дарья",
            industry="HoReCa",
            balance="18 000",
            avg_daily_income="4 100",
            upcoming_expenses="95 000",
            gap_date="2026-08-19",
            gap_amount="-12 400",
            recommended_product="Овердрафт под прогноз выручки",
        ),
        "eligibility_explainer": dict(
            client_name="Дарья Кузнецова",
            entity_type="ИП",
            industry="производство хлебобулочных изделий",
            program_name="Грант на развитие сельского хозяйства",
            organizer="Минсельхоз региона",
            verdict="подходит",
            reason="Открытый приём заявок, возраст клиента входит в диапазон 14-35 лет.",
        ),
        "application_draft": dict(
            program_name="Грант на развитие сельского хозяйства",
            organizer="Минсельхоз региона",
            client_name="Дарья Кузнецова",
            entity_type="ИП",
            industry="производство хлебобулочных изделий",
            region="Ленинградская область",
            registered_at="2024-03-01",
            missing_documents="бизнес-план, документ на помещение",
        ),
        "documents_request": dict(
            client_name="Дарья Кузнецова",
            program_name="Грант на развитие сельского хозяйства",
            available_documents="выписка по счёту, справка об отсутствии задолженности",
            missing_documents="бизнес-план, документ на помещение",
        ),
    }

    registered = set(list_templates())
    untested = registered - set(samples)
    if untested:
        print(f"[!] Нет тестовых данных для шаблонов: {sorted(untested)}")

    for name, kwargs in samples.items():
        system, user = render(name, **kwargs)
        assert system and user, name
        assert "{" not in user, f"в {name} остался неподставленный плейсхолдер"
        print(f"[v] {name}: system {len(system)} симв., user {len(user)} симв.")


def check_live_call() -> None:
    print("\n=== 3. Реальный вызов модели ===")
    client = get_client()
    system, user = render(
        "cashflow_alert",
        client_name="Дарья",
        gap_date="19 августа 2026",
        gap_amount="-12 400",
        confidence="0.72",
        severity="high",
    )
    text = client.generate(system=system, user=user, max_tokens=200)
    print("\n--- ответ модели ---")
    print(text)
    print("--- конец ответа ---")

    if any(marker in text for marker in ("**", "##", "- ")):
        print("[!] В ответе есть markdown — стоит усилить запрет в промпте")
    else:
        print("[v] Формат чистый, без markdown")


def main() -> int:
    check_config()
    check_prompts()
    try:
        check_live_call()
    except LLMError as exc:
        print(f"\n[X] Вызов не прошёл: {type(exc).__name__}: {exc}")
        return 1
    print("\n[v] LLM-слой работает.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
