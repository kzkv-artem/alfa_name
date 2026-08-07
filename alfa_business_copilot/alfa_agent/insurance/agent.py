from __future__ import annotations

from alfa_agent.insurance.features import ClientFeatures
from alfa_agent.insurance.scoring import InsuranceAssessment, InsuranceRecommendation, recommend
from alfa_agent.llm import LLMClient, get_client, render

REASON_TEXT = {
    "HAS_RENT": "у вас регулярные платежи за аренду",
    "HAS_PREMISES": "у вас есть помещение",
    "OWNS_EQUIPMENT": "у вас есть дорогое оборудование",
    "HIGH_EQUIPMENT_SPEND": "вы вложились в оборудование на крупную сумму",
    "EQUIPMENT_HEAVY": "оборудование — существенная доля ваших расходов",
    "RECENT_PURCHASE": "оборудование куплено совсем недавно",
    "FOOT_TRAFFIC": "через вас проходит много клиентов",
    "SERVICE_ON_CLIENT": "вы оказываете услуги, связанные с телом клиента",
    "HAS_STAFF": "у вас есть штат сотрудников",
    "IT_SPEND": "вы тратите на IT, хостинг и подписки",
    "ONLINE_REVENUE": "заметная доля выручки идёт через интернет",
    "ALREADY_INSURED": "у вас уже есть похожая страховка",
    "RENEWAL_WINDOW": "срок вашей прошлой страховки подходит к концу",
}


def _reasons_text(codes: tuple[str, ...]) -> str:
    phrases = [REASON_TEXT.get(code, code) for code in codes]
    return "; ".join(phrases) if phrases else "по данным о бизнесе"


def _format_recommendation(rec: InsuranceRecommendation) -> str:
    p = rec.product
    return (
        f"{p.client_name} ({p.official_name})\n"
        f"От чего защищает: {p.protects_against}\n"
        f"Почему именно вам: {_reasons_text(rec.reason_codes)}\n"
        f"Стоимость: {p.price_hint}\n"
        f"Как оформить: {p.registration_note}\n"
        f"Что не покрыто: {p.exclusions or 'нет данных'}"
    )


def _format_recommendations(recs: tuple[InsuranceRecommendation, ...]) -> str:
    return "\n\n".join(_format_recommendation(r) for r in recs)


class InsuranceAdvisorAgent:

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_client()

    def recommend_and_explain(
        self, features: ClientFeatures
    ) -> tuple[str | None, InsuranceAssessment]:
        assessment = recommend(features)
        if not assessment.recommendations:
            return None, assessment
        return self._explain(assessment), assessment

    def answer_followup(self, user_message: str, assessment: InsuranceAssessment) -> str:
        system, user = render(
            "insurance_followup",
            recommendations=_format_recommendations(assessment.recommendations),
            user_message=user_message,
        )
        return self.llm_client.generate(system=system, user=user)

    def _explain(self, assessment: InsuranceAssessment) -> str:
        system, user = render(
            "insurance_recommendation",
            urgency="повышенная" if assessment.urgency == "high" else "обычная",
            coverage_config=assessment.coverage_config,
            recommendations=_format_recommendations(assessment.recommendations),
        )
        return self.llm_client.generate(system=system, user=user)
