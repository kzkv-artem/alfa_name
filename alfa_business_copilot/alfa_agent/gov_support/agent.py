from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from alfa_agent.gov_support.matching import available_documents, decide, missing_documents
from alfa_agent.llm import LLMClient, get_client, render


@dataclass(frozen=True)
class ProgramAdvice:

    program_id: int
    program_name: str
    is_eligible: bool
    reason: str
    decision: str
    missing_documents: tuple[str, ...]
    explanation: str


class GovSupportAgent:

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_client()

    def advise(
        self, conn: sqlite3.Connection, client: sqlite3.Row, program: sqlite3.Row,
        is_eligible: bool, reason: str,
    ) -> ProgramAdvice:
        missing = missing_documents(conn, client["client_id"], program["program_id"]) if is_eligible else []
        decision = decide(is_eligible, missing)
        explanation = self.explain_eligibility(client, program, is_eligible, reason)
        return ProgramAdvice(
            program_id=program["program_id"], program_name=program["name"],
            is_eligible=is_eligible, reason=reason, decision=decision,
            missing_documents=tuple(missing), explanation=explanation,
        )

    def explain_eligibility(
        self, client: sqlite3.Row, program: sqlite3.Row, is_eligible: bool, reason: str,
    ) -> str:
        system, user = render(
            "eligibility_explainer",
            client_name=client["full_name"],
            entity_type=client["entity_type"],
            industry=client["industry_code"],
            program_name=program["name"],
            organizer=program["organizer"],
            verdict="подходит" if is_eligible else "не подходит",
            reason=reason,
        )
        return self.llm_client.generate(system=system, user=user)

    def draft_application(
        self, client: sqlite3.Row, program: sqlite3.Row, missing: list[str],
    ) -> str:
        missing_str = ", ".join(missing) if missing else "нет — все документы уже есть у банка"
        system, user = render(
            "application_draft",
            program_name=program["name"],
            organizer=program["organizer"],
            client_name=client["full_name"],
            entity_type=client["entity_type"],
            industry=client["industry_code"],
            region=client["region_code"],
            registered_at=client["business_registered_at"],
            missing_documents=missing_str,
        )
        return self.llm_client.generate(system=system, user=user)

    def request_documents(
        self, conn: sqlite3.Connection, client: sqlite3.Row, program: sqlite3.Row,
    ) -> str:
        available = available_documents(conn, client["client_id"], program["program_id"])
        missing = missing_documents(conn, client["client_id"], program["program_id"])
        system, user = render(
            "documents_request",
            client_name=client["full_name"],
            program_name=program["name"],
            available_documents=", ".join(available) if available else "пока ничего",
            missing_documents=", ".join(missing),
        )
        return self.llm_client.generate(system=system, user=user)
