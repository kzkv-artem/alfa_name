from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProgramMatchOut(BaseModel):
    program_id: int
    program_name: str
    is_eligible: bool
    reason: str


class ProgramAdviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    program_id: int
    program_name: str
    is_eligible: bool
    reason: str
    decision: str
    missing_documents: tuple[str, ...]
    explanation: str


class DraftOut(BaseModel):
    draft_text: str


class DocumentsRequestOut(BaseModel):
    text: str
