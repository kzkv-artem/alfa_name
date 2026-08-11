from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response

from alfa_agent.gov_support import GovSupportAgent, decide, missing_documents
from alfa_agent.gov_support.matching import check_eligibility
from alfa_agent.gov_support.pdf_export import build_draft_pdf

from api.deps import get_gov_agent, get_gov_client_id, get_gov_conn
from api.schemas.gov_support import (
    DocumentsRequestOut,
    DraftOut,
    ProgramAdviceOut,
    ProgramMatchListOut,
    ProgramMatchOut,
)

router = APIRouter(prefix="/gov_support", tags=["gov_support"])

# Прямые ссылки на страницу конкретной программы, а не на корень домена
# (в отличие от raw_program_source.source_url — это то, что было доступно
# для парсинга колонки "Источник" в CSV). Найдено вручную для части
# программ там, где у организатора реально есть отдельная страница —
# остальные 20 программ либо не имеют выделенной страницы вообще (заявка
# только через личный кабинет на портале), либо не проверялись: для них
# используется source_url как есть.
PROGRAM_URL_OVERRIDES: dict[str, str] = {
    "fsi-student-startup": "https://fasie.ru/programs/programma-studstartup/",
    "fsi-start-1": "https://fasie.ru/programs/programma-start/",
    "fsi-start": "https://fasie.ru/programs/programma-start/",
    "program-1764": "https://invest.economy.gov.ru/programma-lgotnogo-kreditovaniya-subektov-msp-programma-1764-",
    "umbrella-guarantee": "https://corpmsp.ru/to-banks/zontichnyy-mekhanizm/",
    "my-business-centers": "https://мойбизнес.рф/about/",
}

_PROGRAM_QUERY = """
    SELECT sp.*, rps.external_id, rps.source_url
    FROM support_program sp
    JOIN raw_program_source rps ON rps.source_row_id = sp.raw_source_id
"""


def _resolve_url(program: sqlite3.Row) -> str:
    return PROGRAM_URL_OVERRIDES.get(program["external_id"], program["source_url"] or "")


def _get_client(conn: sqlite3.Connection, client_id: int) -> sqlite3.Row:
    client = conn.execute("SELECT * FROM client WHERE client_id = ?", (client_id,)).fetchone()
    if client is None:
        raise HTTPException(404, f"Клиент {client_id} не найден")
    return client


def _get_program(conn: sqlite3.Connection, program_id: int) -> sqlite3.Row:
    program = conn.execute(
        f"{_PROGRAM_QUERY} WHERE sp.program_id = ?", (program_id,)
    ).fetchone()
    if program is None:
        raise HTTPException(404, f"Программа {program_id} не найдена")
    return program


def _virtual_client(description: str) -> dict:
    """Для поиска по свободному описанию — без записи в БД, без реального
    client_id. check_eligibility читает только birth_date и industry_code,
    ей всё равно, sqlite3.Row это или dict. Возраст не известен — берём
    условно 30 лет, чтобы программы под конкретную возрастную группу
    (14-25/14-35, студенты) не засчитывались как подходящие вслепую.
    Отрасль — буквально то, что написал пользователь: check_eligibility
    и так сравнивает industry_code нечётким совпадением по словам/подстроке,
    у Алины и Дарьи в БД там тоже просто свободный текст, а не код."""
    return {
        "full_name": "Ваш бизнес",
        "entity_type": "не указана",
        "industry_code": description,
        "birth_date": (date.today() - timedelta(days=365 * 30)).isoformat(),
    }


@router.get("/programs", response_model=ProgramMatchListOut)
def list_programs(
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_client_id),
) -> ProgramMatchListOut:
    client = _get_client(conn, client_id)
    as_of = date.today().isoformat()
    programs = conn.execute(_PROGRAM_QUERY).fetchall()
    programs_with_docs = {
        row["program_id"]
        for row in conn.execute("SELECT DISTINCT program_id FROM required_document").fetchall()
    }
    eligible, not_eligible = [], []
    for program in programs:
        is_eligible, reason = check_eligibility(client, program, as_of)
        match = ProgramMatchOut(
            program_id=program["program_id"],
            program_name=program["name"],
            is_eligible=is_eligible,
            reason=reason,
            source_url=_resolve_url(program),
        )
        (eligible if is_eligible else not_eligible).append(match)
    # Программы с реальным списком документов (required_document, т.е. то, что
    # заведено в REQUIRED_DOCS_BY_PROGRAM) — наверх. `programs` уже отдан из БД
    # по возрастанию program_id, а list.sort() в Python устойчив, так что внутри
    # каждой из двух групп порядок остаётся тем же самым между запусками.
    eligible.sort(key=lambda m: m.program_id not in programs_with_docs)
    return ProgramMatchListOut(eligible=eligible, not_eligible=not_eligible)


@router.get("/programs/{program_id}/advice", response_model=ProgramAdviceOut)
def get_advice(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_client_id),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> ProgramAdviceOut:
    client = _get_client(conn, client_id)
    program = _get_program(conn, program_id)
    is_eligible, reason = check_eligibility(client, program, date.today().isoformat())
    advice = agent.advise(conn, client, program, is_eligible, reason)
    return ProgramAdviceOut(
        program_id=advice.program_id,
        program_name=advice.program_name,
        is_eligible=advice.is_eligible,
        reason=advice.reason,
        decision=advice.decision,
        missing_documents=advice.missing_documents,
        explanation=advice.explanation,
        source_url=_resolve_url(program),
    )


@router.get("/match", response_model=ProgramMatchListOut)
def match_by_description(
    description: str,
    conn: sqlite3.Connection = Depends(get_gov_conn),
) -> ProgramMatchListOut:
    """То же, что /programs, но без привязки к зарегистрированному клиенту —
    для поля «опишите бизнес своими словами» в кабинете. PDF-черновик тут
    сознательно не предлагается: заявителя без имени в БД нет, оформлять
    черновик не для кого."""
    description = description.strip()
    if not description:
        raise HTTPException(400, "Опишите бизнес — поле не должно быть пустым")
    client = _virtual_client(description)
    as_of = date.today().isoformat()
    programs = conn.execute(_PROGRAM_QUERY).fetchall()
    eligible, not_eligible = [], []
    for program in programs:
        is_eligible, reason = check_eligibility(client, program, as_of)
        match = ProgramMatchOut(
            program_id=program["program_id"],
            program_name=program["name"],
            is_eligible=is_eligible,
            reason=reason,
            source_url=_resolve_url(program),
        )
        (eligible if is_eligible else not_eligible).append(match)
    return ProgramMatchListOut(eligible=eligible, not_eligible=not_eligible)


@router.get("/match/{program_id}/advice", response_model=ProgramAdviceOut)
def match_advice(
    program_id: int,
    description: str,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> ProgramAdviceOut:
    description = description.strip()
    if not description:
        raise HTTPException(400, "Опишите бизнес — поле не должно быть пустым")
    program = _get_program(conn, program_id)
    client = _virtual_client(description)
    is_eligible, reason = check_eligibility(client, program, date.today().isoformat())
    explanation = agent.explain_eligibility(client, program, is_eligible, reason)
    return ProgramAdviceOut(
        program_id=program["program_id"],
        program_name=program["name"],
        is_eligible=is_eligible,
        reason=reason,
        decision="eligible" if is_eligible else "not_eligible",
        missing_documents=(),
        explanation=explanation,
        source_url=_resolve_url(program),
    )


@router.post("/programs/{program_id}/draft", response_model=DraftOut)
def draft(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_client_id),
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


@router.post("/programs/{program_id}/draft.pdf")
def draft_pdf(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_client_id),
    agent: GovSupportAgent = Depends(get_gov_agent),
) -> Response:
    client = _get_client(conn, client_id)
    program = _get_program(conn, program_id)
    is_eligible, _reason = check_eligibility(client, program, date.today().isoformat())
    missing = missing_documents(conn, client_id, program_id) if is_eligible else []
    if decide(is_eligible, missing) != "propose_draft":
        raise HTTPException(409, "Для этой программы черновик не предлагается — проверьте /advice")
    text = agent.draft_application(client, program, missing)
    pdf_bytes = build_draft_pdf(client, program, missing, text)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="draft_program_{program_id}.pdf"'},
    )


@router.post("/programs/{program_id}/request-documents", response_model=DocumentsRequestOut)
def request_documents(
    program_id: int,
    conn: sqlite3.Connection = Depends(get_gov_conn),
    client_id: int = Depends(get_gov_client_id),
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
