from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from alfa_agent.insurance import ClientFeatures, InsuranceAdvisorAgent

from api.deps import get_insurance_agent, get_insurance_features_index
from api.schemas.insurance import (
    AssessmentOut,
    FollowupRequest,
    FollowupResponse,
    InsuranceClientOut,
    RecommendResponse,
)
from api.sessions import insurance_sessions

router = APIRouter(prefix="/insurance", tags=["insurance"])


@router.get("/clients", response_model=list[InsuranceClientOut])
def list_clients(
    features_index: dict[str, ClientFeatures] = Depends(get_insurance_features_index),
) -> list[InsuranceClientOut]:
    return [
        InsuranceClientOut(client_id=f.client_id, legal_form=f.legal_form, okved=f.okved)
        for f in features_index.values()
    ]


@router.get("/clients/{client_id}/recommendation", response_model=RecommendResponse)
def get_recommendation(
    client_id: str,
    features_index: dict[str, ClientFeatures] = Depends(get_insurance_features_index),
    agent: InsuranceAdvisorAgent = Depends(get_insurance_agent),
) -> RecommendResponse:
    features = features_index.get(client_id)
    if features is None:
        raise HTTPException(404, f"Клиент {client_id!r} не найден")
    reply, assessment = agent.recommend_and_explain(features)
    session_id = insurance_sessions.create(assessment)
    return RecommendResponse(
        session_id=session_id,
        reply=reply,
        assessment=AssessmentOut.model_validate(assessment),
    )


@router.post("/sessions/{session_id}/followup", response_model=FollowupResponse)
def followup(
    session_id: str,
    body: FollowupRequest,
    agent: InsuranceAdvisorAgent = Depends(get_insurance_agent),
) -> FollowupResponse:
    assessment = insurance_sessions.get(session_id)
    if assessment is None:
        raise HTTPException(404, f"Сессия {session_id!r} не найдена или истекла")
    reply = agent.answer_followup(body.message, assessment)
    return FollowupResponse(reply=reply)
