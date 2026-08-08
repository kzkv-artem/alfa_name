"""Одноразовая разметка industry_allowed/entity_type_allowed по всем 20
программам через LLM — ОДИН запрос на все программы разом, не 20 отдельных
(двадцать отдельных вызовов упирались в дневной лимит бесплатной модели).
Не часть рантайма — только черновик, который после ручной проверки
зашивается в normalize.py статикой.

Запуск: ./.venv/Scripts/python.exe scripts/extract_program_restrictions.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alfa_agent.llm import get_client

CSV_PATH = PROJECT_ROOT / "otbor" / "mery-podderzhki-msp-2026.csv"
OUT_PATH = PROJECT_ROOT / "otbor" / "program_restrictions_draft.json"

SYSTEM = """Ты размечаешь меры господдержки бизнеса для системы подбора программ.
Тебе дан список программ, для каждой — id, название, аудитория, ключевые условия.

Для КАЖДОЙ программы из списка определи два поля:
- industry_allowed: список отраслевых ограничений на русском, короткими фразами
  (например ["сельское хозяйство"], ["ИТ"]). Пустой список [], если в тексте
  нет отраслевого ограничения — НЕ выдумывай ограничение, которого нет в тексте.
- entity_type_allowed: список организационно-правовых форм, которым доступна
  программа, СТРОГО из набора ["ИП","ООО","самозанятый","физлицо"] — используй
  только эти четыре значения, ничего другого. Пустой список [], если по тексту
  ограничений на организационно-правовую форму нет (например, просто "МСП" без
  уточнения — это не ограничение формы, а требование по масштабу бизнеса).

Ответь строго ОДНИМ JSON-объектом вида:
{"programs": [{"id": "<id программы>", "industry_allowed": [...], "entity_type_allowed": [...]}, ...]}
— ровно по одному элементу на каждую программу из входного списка, в том же
порядке и с теми же id. Больше ничего в ответе быть не должно."""


def build_user_prompt(rows: list[dict]) -> str:
    blocks = []
    for r in rows:
        blocks.append(
            f"id: {r['id']}\n"
            f"Программа: {r['Мера']}\n"
            f"Аудитория: {r.get('Аудитория') or '(не указано)'}\n"
            f"Ключевые условия: {r.get('Ключевые_условия') or '(не указано)'}"
        )
    return f"Программ: {len(rows)}\n\n" + "\n\n".join(blocks)


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    client = get_client()
    user = build_user_prompt(rows)

    # дефолтный max_tokens (800) рассчитан на разговорные ответы, а не на
    # JSON с 20 объектами разом — поднимаем, чтобы ответ не обрезался.
    data = client.generate_json(system=SYSTEM, user=user, max_tokens=3000)
    by_id = {p.get("id"): p for p in data.get("programs", [])}

    results = []
    missing = []
    for r in rows:
        p = by_id.get(r["id"])
        if p is None:
            missing.append(r["id"])
            industry, entity = None, None
        else:
            industry = p.get("industry_allowed", [])
            entity = p.get("entity_type_allowed", [])
        results.append({
            "id": r["id"], "name": r["Мера"],
            "audience": r.get("Аудитория", ""), "key_conditions": r.get("Ключевые_условия", ""),
            "industry_allowed": industry, "entity_type_allowed": entity,
        })

    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Сохранено: {OUT_PATH}")
    print(f"Программ в CSV: {len(rows)}, получено ответов от LLM: {len(by_id)}")
    if missing:
        print(f"НЕ нашлось в ответе LLM (id): {missing}")

    print()
    print(f"{'id':28} {'industry_allowed':35} {'entity_type_allowed':25}")
    print("-" * 90)
    for r in results:
        print(f"{r['id']:28} {str(r['industry_allowed']):35} {str(r['entity_type_allowed']):25}")


if __name__ == "__main__":
    main()
