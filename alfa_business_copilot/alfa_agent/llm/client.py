from __future__ import annotations

import json
import logging
import random
import re
import time
from abc import ABC, abstractmethod

from alfa_agent.llm.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMConfigError(LLMError):
    pass


class LLMUnavailableError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


class LLMClient(ABC):

    @abstractmethod
    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        pass

    @abstractmethod
    def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        pass


class DeepSeekClient(LLMClient):

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()
        self._validate_config()
        self._client = self._build_sdk_client()
        logger.info("LLM-клиент инициализирован: %s", self.config.describe())


    def _validate_config(self) -> None:
        cfg = self.config
        if not cfg.api_key:
            raise LLMConfigError(
                f"Не задан ключ доступа к LLM. Положите его в переменную окружения "
                f"{cfg.key_env_var} (или LLM_API_KEY) — например, в файл .env."
            )
        if not cfg.model:
            raise LLMConfigError("Не задано имя модели (LLM_MODEL).")
        if not cfg.base_url:
            raise LLMConfigError("Не задан base_url провайдера (LLM_BASE_URL).")

    def _build_sdk_client(self):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigError(
                "Не установлен пакет openai. Установите зависимости: "
                "pip install -r requirements.txt"
            ) from exc

        return OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=0,
        )


    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        text = self._complete(
            system=system,
            user=user,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )
        if not text.strip():
            raise LLMResponseError("Модель вернула пустой ответ.")
        return text.strip()

    def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        raw = self._complete(
            system=system,
            user=user,
            temperature=temperature if temperature is not None else 0.0,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return _parse_json_object(raw)


    def _complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None,
        max_tokens: int | None,
        json_mode: bool,
    ) -> str:
        cfg = self.config
        payload = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": cfg.temperature if temperature is None else temperature,
            "max_tokens": cfg.max_tokens if max_tokens is None else max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None

        for attempt in range(cfg.max_retries + 1):
            try:
                started = time.monotonic()
                response = self._client.chat.completions.create(**payload)
                elapsed = time.monotonic() - started

                usage = getattr(response, "usage", None)
                logger.info(
                    "LLM ok: model=%s attempt=%d elapsed=%.2fs tokens_in=%s tokens_out=%s",
                    cfg.model,
                    attempt + 1,
                    elapsed,
                    getattr(usage, "prompt_tokens", "?"),
                    getattr(usage, "completion_tokens", "?"),
                )
                return response.choices[0].message.content or ""

            except Exception as exc:
                last_error = exc
                if not _is_retryable(exc):
                    logger.error("LLM: неповторяемая ошибка — %s", _short(exc))
                    raise _wrap_fatal(exc) from exc

                if attempt >= cfg.max_retries:
                    break

                pause = _backoff_delay(attempt, cfg.backoff_base, cfg.backoff_max)
                logger.warning(
                    "LLM: попытка %d/%d не удалась (%s). Повтор через %.1f с.",
                    attempt + 1,
                    cfg.max_retries + 1,
                    _short(exc),
                    pause,
                )
                time.sleep(pause)

        raise LLMUnavailableError(
            f"Модель недоступна после {cfg.max_retries + 1} попыток. "
            f"Последняя ошибка: {_short(last_error)}"
        ) from last_error


class StubLLMClient(LLMClient):

    def __init__(self, text: str = "test-response", payload: dict | None = None) -> None:
        self.text = text
        self.payload = payload if payload is not None else {}
        self.calls: list[dict] = []

    def generate(self, system: str, user: str, **kwargs) -> str:
        self.calls.append({"system": system, "user": user, "mode": "text", **kwargs})
        return self.text

    def generate_json(self, system: str, user: str, **kwargs) -> dict:
        self.calls.append({"system": system, "user": user, "mode": "json", **kwargs})
        return self.payload


_RETRYABLE_NAMES = {
    "APITimeoutError",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
    "APIResponseValidationError",
    "Timeout",
    "ConnectionError",
}


def _is_retryable(exc: Exception) -> bool:
    if type(exc).__name__ in _RETRYABLE_NAMES:
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 429 or status >= 500
    return False


def _wrap_fatal(exc: Exception) -> LLMError:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return LLMConfigError(
            f"Провайдер отклонил ключ доступа (HTTP {status}). Проверьте ключ и права."
        )
    if status == 404:
        return LLMConfigError(
            "Провайдер не знает такую модель или адрес (HTTP 404). "
            "Проверьте LLM_MODEL и LLM_BASE_URL."
        )
    if status == 400:
        return LLMResponseError(f"Провайдер отверг запрос (HTTP 400): {_short(exc)}")
    return LLMUnavailableError(f"Ошибка обращения к модели: {_short(exc)}")


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    raw = min(cap, base * (2**attempt))
    return raw * (0.5 + random.random() / 2)


def _short(exc: Exception | None, limit: int = 200) -> str:
    if exc is None:
        return "неизвестна"
    text = f"{type(exc).__name__}: {exc}"
    return text if len(text) <= limit else text[: limit - 1] + "…"


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_object(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise LLMResponseError("Модель вернула пустой ответ вместо JSON.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if not match:
            raise LLMResponseError(f"В ответе модели нет JSON: {text[:200]!r}") from None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"Сломанный JSON в ответе модели: {exc}") from exc

    if not isinstance(parsed, dict):
        raise LLMResponseError(f"Ожидался JSON-объект, получен {type(parsed).__name__}.")
    return parsed


_client: LLMClient | None = None


def get_client(config: LLMConfig | None = None) -> LLMClient:
    global _client
    if config is not None:
        return DeepSeekClient(config)
    if _client is None:
        _client = DeepSeekClient()
    return _client


def set_client(client: LLMClient) -> None:
    global _client
    _client = client


def reset_client() -> None:
    global _client
    _client = None
