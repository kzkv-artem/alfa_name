from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from alfa_agent.gov_support import GovSupportAgent, build_database, run_matching
from alfa_agent.gov_support.fixtures import seed_demo_data
from alfa_agent.gov_support.ingest import load_raw_programs
from alfa_agent.gov_support.normalize import normalize_programs
from alfa_agent.llm import LLMError

AS_OF = "2026-07-19"


def main() -> None:
    conn = build_database()
    n_raw = load_raw_programs(conn)
    normalize_programs(conn)
    client_id, _ = seed_demo_data(conn)
    print(f"Программ загружено: {n_raw}")

    results = run_matching(conn, client_id, AS_OF)
    n_eligible = sum(1 for r in results if r["is_eligible"])
    print(f"Подходит клиенту: {n_eligible} из {len(results)}")

    client = conn.execute("SELECT * FROM client WHERE client_id=?", (client_id,)).fetchone()
    agent = GovSupportAgent()

    for r in results:
        program = r["program"]
        try:
            advice = agent.advise(conn, client, program, r["is_eligible"], r["reason"])
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")
            continue

        print(f"\n=== {program['name']} ===")
        print(advice.explanation)

        try:
            if advice.decision == "propose_draft":
                print("--- черновик заявления ---")
                print(agent.draft_application(client, program, list(advice.missing_documents)))
            elif advice.decision == "request_documents":
                print("--- запрос документов ---")
                print(agent.request_documents(conn, client, program))
        except LLMError as exc:
            print(f"[Ошибка LLM] {exc}")


if __name__ == "__main__":
    main()
