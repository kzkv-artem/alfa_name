from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from alfa_agent.llm import LLMConfigError, LLMError, LLMResponseError, LLMUnavailableError


def _error_response(status_code: int, error: str, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "message": str(exc)})


def register_error_handlers(app: FastAPI) -> None:
    """LLMError and its subclasses are what every agent method already raises on
    any LLM problem (see alfa_agent/llm/client.py) — map them to HTTP once here
    instead of try/except-ing them in every route."""

    @app.exception_handler(LLMConfigError)
    async def _config_error(request: Request, exc: LLMConfigError) -> JSONResponse:
        return _error_response(503, "llm_config_error", exc)

    @app.exception_handler(LLMUnavailableError)
    async def _unavailable_error(request: Request, exc: LLMUnavailableError) -> JSONResponse:
        return _error_response(503, "llm_unavailable", exc)

    @app.exception_handler(LLMResponseError)
    async def _response_error(request: Request, exc: LLMResponseError) -> JSONResponse:
        return _error_response(502, "llm_response_error", exc)

    @app.exception_handler(LLMError)
    async def _generic_llm_error(request: Request, exc: LLMError) -> JSONResponse:
        return _error_response(500, "llm_error", exc)
