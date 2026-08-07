from __future__ import annotations

from fastapi import APIRouter, Depends

from alfa_agent.acquisition import RiskAdvisorAgent, RiskChatState

from api.deps import get_acquisition_agent
from api.schemas.acquisition import ChatRequest, ChatResponse, RiskChatStateOut
from api.sessions import acquisition_sessions

router = APIRouter(prefix="/acquisition", tags=["acquisition"])


@router.post("/messages", response_model=ChatResponse)
def send_message(
    body: ChatRequest,
    agent: RiskAdvisorAgent = Depends(get_acquisition_agent),
) -> ChatResponse:
    session_id, state = acquisition_sessions.get_or_create(body.session_id, RiskChatState)
    reply, new_state = agent.handle_message(body.message, state)
    acquisition_sessions.set(session_id, new_state)
    return ChatResponse(
        session_id=session_id,
        reply=reply,
        state=RiskChatStateOut.model_validate(new_state),
    )
