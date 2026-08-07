from __future__ import annotations

import sqlite3
from datetime import date

DRAFT_THRESHOLD = 2


def client_age(birth_date: str, as_of: str) -> int:
    b, a = date.fromisoformat(birth_date), date.fromisoformat(as_of)
    return a.year - b.year - ((a.month, a.day) < (b.month, b.day))


def check_eligibility(client: sqlite3.Row, program: sqlite3.Row, as_of: str) -> tuple[bool, str]:
    if not program["is_open"]:
        return False, "Приём заявок по этой программе сейчас закрыт или требует уточнения статуса."
    if program["age_min"] is not None or program["age_max"] is not None:
        age = client_age(client["birth_date"], as_of)
        lo, hi = program["age_min"] or 0, program["age_max"] or 200
        if not (lo <= age <= hi):
            return False, f"Возраст клиента ({age}) не входит в диапазон {lo}-{hi} лет."
    return True, "Клиент проходит по всем распознанным критериям (открытый приём, возраст)."


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
