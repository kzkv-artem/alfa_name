from __future__ import annotations

import json
import sqlite3
from datetime import date

DRAFT_THRESHOLD = 2


def client_age(birth_date: str, as_of: str) -> int:
    b, a = date.fromisoformat(birth_date), date.fromisoformat(as_of)
    return a.year - b.year - ((a.month, a.day) < (b.month, b.day))


def _industry_matches(industry_allowed_json: str | None, client_industry: str | None) -> bool:
    """industry_allowed — короткие русские фразы от LLM (см. normalize.py),
    client.industry_code — свободный текст. Точного словаря нет ни у кого,
    поэтому сравниваем подстрокой в обе стороны и пересечением по словам —
    грубее semantic-match, но без лишнего LLM-вызова в рантайме. Пустой
    список — программа без отраслевого ограничения, доступна всем."""
    allowed = json.loads(industry_allowed_json) if industry_allowed_json else []
    if not allowed:
        return True
    if not client_industry:
        return False
    client_lower = client_industry.lower()
    client_words = set(client_lower.replace(",", " ").split())
    for phrase in allowed:
        phrase_lower = phrase.lower()
        if phrase_lower in client_lower or client_lower in phrase_lower:
            return True
        if set(phrase_lower.split()) & client_words:
            return True
    return False


def check_eligibility(client: sqlite3.Row, program: sqlite3.Row, as_of: str) -> tuple[bool, str]:
    if not program["is_open"]:
        return False, "Приём заявок по этой программе сейчас закрыт или требует уточнения статуса."
    if program["age_min"] is not None or program["age_max"] is not None:
        age = client_age(client["birth_date"], as_of)
        lo, hi = program["age_min"] or 0, program["age_max"] or 200
        if not (lo <= age <= hi):
            return False, f"Возраст клиента ({age}) не входит в диапазон {lo}-{hi} лет."
    if not _industry_matches(program["industry_allowed"], client["industry_code"]):
        allowed = json.loads(program["industry_allowed"]) if program["industry_allowed"] else []
        return False, f"Программа рассчитана на другие отрасли: {', '.join(allowed)}."
    return True, "Клиент проходит по всем распознанным критериям (открытый приём, возраст, отрасль)."


def run_matching(conn: sqlite3.Connection, client_id: int, as_of: str) -> list[dict]:
    client = conn.execute("SELECT * FROM client WHERE client_id=?", (client_id,)).fetchone()
    programs = conn.execute("SELECT * FROM support_program").fetchall()
    results = []
    for program in programs:
        is_eligible, reason = check_eligibility(client, program, as_of)
        conn.execute(
            "INSERT INTO eligibility_check (client_id, program_id, is_eligible, reason_text) VALUES (?,?,?,?)",
            (client_id, program["program_id"], int(is_eligible), reason),
        )
        results.append({"program": program, "is_eligible": is_eligible, "reason": reason})
    conn.commit()
    return results


def missing_documents(conn: sqlite3.Connection, client_id: int, program_id: int) -> list[str]:
    rows = conn.execute(
        """SELECT dt.name FROM required_document rd
           JOIN document_type dt ON dt.document_type_id = rd.document_type_id
           WHERE rd.program_id = ?
             AND rd.document_type_id NOT IN (
                 SELECT cd.document_type_id FROM client_document cd
                 WHERE cd.client_id = ? AND cd.status = 'verified'
             )""",
        (program_id, client_id),
    ).fetchall()
    return [r["name"] for r in rows]


def available_documents(conn: sqlite3.Connection, client_id: int, program_id: int) -> list[str]:
    rows = conn.execute(
        """SELECT dt.name FROM required_document rd
           JOIN document_type dt ON dt.document_type_id = rd.document_type_id
           WHERE rd.program_id = ?
             AND rd.document_type_id IN (
                 SELECT cd.document_type_id FROM client_document cd
                 WHERE cd.client_id = ? AND cd.status = 'verified'
             )""",
        (program_id, client_id),
    ).fetchall()
    return [r["name"] for r in rows]


def decide(is_eligible: bool, missing: list[str]) -> str:
    if not is_eligible:
        return "not_eligible"
    if len(missing) <= DRAFT_THRESHOLD:
        return "propose_draft"
    return "request_documents"
