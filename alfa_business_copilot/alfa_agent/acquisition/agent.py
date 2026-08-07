from __future__ import annotations

from dataclasses import dataclass

from alfa_agent.acquisition import risk_scoring
from alfa_agent.acquisition.reference import (
    INDUSTRY_BY_CODE,
    REGION_BY_CODE,
    get_industry,
    get_region,
    industries_for_prompt,
    regions_for_prompt,
)
from alfa_agent.llm import LLMClient, get_client, render


@dataclass(frozen=True)
class RiskChatState:

    industry_code: str | None = None
    region_code: str | None = None
    budget_rub: int | None = None


def _display_name(code: str | None, lookup) -> str:
    if code is None:
        return "не указано"
    try:
        return lookup(code).name
    except KeyError:
        return "не указано"


def _format_factors(factors: list[risk_scoring.RiskFactor]) -> str:
    if not factors:
        return "особо выделить нечего"
    return "\n".join(f"- {f.name}: {f.comment} ({f.display})" for f in factors)


class RiskAdvisorAgent:

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_client()

    def handle_message(
        self, user_message: str, state: RiskChatState | None = None
    ) -> tuple[str, RiskChatState]:
        state = state or RiskChatState()
        new_state = self._extract(user_message, state)

        missing = self._missing_fields(new_state)
        if missing:
            question = self._ask_clarifying(new_state, missing)
            return question, new_state

        assessment = risk_scoring.assess(
            new_state.industry_code, new_state.region_code, new_state.budget_rub
        )
        answer = self._explain(assessment)
        return answer, new_state


    def _extract(self, user_message: str, state: RiskChatState) -> RiskChatState:
        system, user = render(
            "risk_entity_extraction",
            industries=industries_for_prompt(),
            regions=regions_for_prompt(),
            known_industry=state.industry_code or "нет данных",
            known_region=state.region_code or "нет данных",
            known_budget=str(state.budget_rub) if state.budget_rub else "нет данных",
            user_message=user_message,
        )
        data = self.llm_client.generate_json(system=system, user=user)

        return RiskChatState(
            industry_code=self._valid_industry(data.get("industry_code")) or state.industry_code,
            region_code=self._valid_region(data.get("region_code")) or state.region_code,
            budget_rub=self._valid_budget(data.get("budget_rub")) or state.budget_rub,
        )

    @staticmethod
    def _valid_industry(code: object) -> str | None:
        return code if isinstance(code, str) and code in INDUSTRY_BY_CODE else None

    @staticmethod
    def _valid_region(code: object) -> str | None:
        return code if isinstance(code, str) and code in REGION_BY_CODE else None

    @staticmethod
    def _valid_budget(value: object) -> int | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return int(value)
        return None


    @staticmethod
    def _missing_fields(state: RiskChatState) -> list[str]:
        missing = []
        if not state.industry_code:
            missing.append("отрасль")
        if not state.region_code:
            missing.append("регион")
        return missing

    def _ask_clarifying(self, state: RiskChatState, missing: list[str]) -> str:
        system, user = render(
            "risk_clarifying_question",
            known_industry=_display_name(state.industry_code, get_industry),
            known_region=_display_name(state.region_code, get_region),
            missing=", ".join(missing),
        )
        return self.llm_client.generate(system=system, user=user)


    def _explain(self, assessment: risk_scoring.RiskAssessment) -> str:
        budget_note = ""
        if assessment.budget_rub:
            budget_note = f"Бюджет клиента: {assessment.budget_rub:,} ₽".replace(",", " ")

        system, user = render(
            "risk_explanation",
            industry=assessment.industry.name,
            region=assessment.region.name,
            score=str(assessment.score),
            level=assessment.level,
            capital=f"{assessment.estimated_capital_rub:,} ₽".replace(",", " "),
            top_risks=_format_factors(assessment.top_risks),
            strengths=_format_factors(assessment.strengths),
            budget_note=budget_note,
        )
        return self.llm_client.generate(system=system, user=user)
