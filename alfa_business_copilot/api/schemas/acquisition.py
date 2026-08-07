from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class RiskChatStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    industry_code: str | None
    region_code: str | None
    budget_rub: int | None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    state: RiskChatStateOut
