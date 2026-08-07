from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import Enum


class Provider(str, Enum):

    DEEPSEEK = "deepseek"
    OPENROUTER = "openrouter"

    @classmethod
    def parse(cls, value: str) -> "Provider":
        try:
            return cls(value.strip().lower())
        except ValueError as exc:
            allowed = ", ".join(p.value for p in cls)
            raise ValueError(
                f"Неизвестный провайдер LLM: {value!r}. Допустимые: {allowed}"
            ) from exc


_PROVIDER_DEFAULTS: dict[Provider, tuple[str, str, str]] = {
    Provider.DEEPSEEK: (
        "https://api.deepseek.com/v1",
        "deepseek-chat",
        "DEEPSEEK_API_KEY",
    ),
    Provider.OPENROUTER: (
        "https://openrouter.ai/api/v1",
        "deepseek/deepseek-chat",
        "OPENROUTER_API_KEY",
    ),
}


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} должен быть числом, получено: {raw!r}") from exc


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} должен быть целым числом, получено: {raw!r}") from exc


@dataclass(frozen=True)
class LLMConfig:

    provider: Provider = Provider.DEEPSEEK
    api_key: str = field(repr=False, default="")
    base_url: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 800
    timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 20.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature должна быть в диапазоне 0.0–2.0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens должен быть положительным")
        if self.timeout <= 0:
            raise ValueError("timeout должен быть положительным")
        if self.max_retries < 0:
            raise ValueError("max_retries не может быть отрицательным")

    @classmethod
    def from_env(cls, provider: str | Provider | None = None) -> "LLMConfig":
        if provider is None:
            provider = _env_str("LLM_PROVIDER", Provider.DEEPSEEK.value) or ""
        resolved = provider if isinstance(provider, Provider) else Provider.parse(provider)

        default_base_url, default_model, key_var = _PROVIDER_DEFAULTS[resolved]
        api_key = _env_str("LLM_API_KEY") or _env_str(key_var) or ""

        return cls(
            provider=resolved,
            api_key=api_key,
            base_url=_env_str("LLM_BASE_URL", default_base_url) or default_base_url,
            model=_env_str("LLM_MODEL", default_model) or default_model,
            temperature=_env_float("LLM_TEMPERATURE", 0.3),
            max_tokens=_env_int("LLM_MAX_TOKENS", 800),
            timeout=_env_float("LLM_TIMEOUT", 30.0),
            max_retries=_env_int("LLM_MAX_RETRIES", 3),
            backoff_base=_env_float("LLM_BACKOFF_BASE", 1.0),
            backoff_max=_env_float("LLM_BACKOFF_MAX", 20.0),
        )

    def with_overrides(self, **kwargs) -> "LLMConfig":
        return replace(self, **kwargs)

    @property
    def key_env_var(self) -> str:
        return _PROVIDER_DEFAULTS[self.provider][2]

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return "<не задан>"
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"

    def describe(self) -> str:
        return (
            f"provider={self.provider.value} model={self.model} "
            f"base_url={self.base_url} key={self.masked_key} "
            f"timeout={self.timeout}s retries={self.max_retries}"
        )
