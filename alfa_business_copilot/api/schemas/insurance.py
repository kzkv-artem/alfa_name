from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InsuranceClientOut(BaseModel):
    client_id: str
    legal_form: str
    okved: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    client_name: str
    official_name: str
    protects_against: str
    price_hint: str
    registration_note: str
    exclusions: str


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product: ProductOut
    need_score: float
    reason_codes: tuple[str, ...]


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    urgency: str
    coverage_config: str
    no_offer_reason: str | None
    recommendations: tuple[RecommendationOut, ...]


class RecommendResponse(BaseModel):
    session_id: str
    reply: str | None
    assessment: AssessmentOut


class FollowupRequest(BaseModel):
    message: str


class FollowupResponse(BaseModel):
    reply: str
