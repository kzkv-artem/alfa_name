from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from alfa_agent.gov_support import GovSupportAgent, decide, missing_documents
from alfa_agent.gov_support.matching import check_eligibility

from api.deps import get_gov_agent, get_gov_conn, get_gov_demo_client_id
from api.schemas.gov_support import DocumentsRequestOut, DraftOut, ProgramAdviceOut, ProgramMatchOut

router = APIRouter(prefix="/gov_support", tags=["gov_support"])


def _get_client(conn: sqlite3.Connection, client_id: int) -> sqlite3.Row:
    client = conn.execute("SELECT * FROM client WHERE client_id = ?", (client_id,)).fetchone()
    if client is None:
        raise HTTPException(404, f"Клиент {client_id} не найден")
    return client


def _get_program(conn: sqlite3.Connection, program_id: int) -> sqlite3.Row:
    program = conn.execute(
        "SELECT * FROM support_program WHERE program_id = ?", (program_id,)
    ).fetchone()
    if program is None:
        raise HTTPException(404, f"Программа {program_id} не найдена")
    return program


@router.get("/programs", response_model=list[ProgramMatchOut])
def list_programs(
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_demo_client_id),
) -> list[ProgramMatchOut]:
    client = _get_client(conn, client_id)
    as_of = date.today().isoformat()
    programs = conn.execute("SELECT * FROM support_program").fetchall()
    out = []
    for program in programs:
        is_eligible, reason = check_eligibility(client, program, as_of)
        out.append(
            ProgramMatchOut(
                program_id=program["program_id"],
                program_name=program["name"],
                is_eligible=is_eligible,
                reason=reason,
            )
        )
    return out


@router.get("/programs/{program_id}/advice", response_model=ProgramAdviceOut)
def get_advice(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_demo_client_id),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> ProgramAdviceOut:
    client = _get_client(conn, client_id)
    program = _get_program(conn, program_id)
    is_eligible, reason = check_eligibility(client, program, date.today().isoformat())
    advice = agent.advise(conn, client, program, is_eligible, reason)
    return ProgramAdviceOut.model_validate(advice)


@router.post("/programs/{program_id}/draft", response_model=DraftOut)
def draft(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_demo_client_id),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> DraftOut:
    client = _get_client(conn, client_id)
    program = _get_program(conn, program_id)
    is_eligible, _reason = check_eligibility(client, program, date.today().isoformat())
    missing = missing_documents(conn, client_id, program_id) if is_eligible else []
    if decide(is_eligible, missing) != "propose_draft":
        raise HTTPException(409, "Для этой программы черновик не предлагается — проверьте /advice")
    text = agent.draft_application(client, program, missing)
    return DraftOut(draft_text=text)


@router.post("/programs/{program_id}/request-documents", response_model=DocumentsRequestOut)
def request_documents(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_demo_client_id),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> DocumentsRequestOut:
    client = _get_client(conn, client_id)
    program = _get_program(conn, program_id)
    is_eligible, _reason = check_eligibility(client, program, date.today().isoformat())
    missing = missing_documents(conn, client_id, program_id) if is_eligible else []
    if decide(is_eligible, missing) != "request_documents":
        raise HTTPException(409, "Для этой программы запрос документов не требуется — проверьте /advice")
    text = agent.request_documents(conn, client, program)
    return DocumentsRequestOut(text=text)
