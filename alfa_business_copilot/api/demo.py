from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alfa_agent.llm import LLMClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES_PATH = PROJECT_ROOT / "demo_fixtures.json"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def is_demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").strip().lower() in _TRUE_VALUES


def fixtures_path() -> Path:
    raw = os.environ.get("DEMO_FIXTURES_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_FIXTURES_PATH


def hash_prompt(system: str, user: str) -> str:
    """Ключ для одной точной пары (system, user). Все 4 демо-сценария
    прогоняются с фиксированными входами, а всё, что определяет промпт ниже
    границы LLM в этом проекте (CatBoost, скоринг страхования, подбор
    программ, риск-скор), детерминировано — значит, один и тот же сценарий
    всегда рендерит один и тот же промпт побайтово, и точное совпадение
    хэша — надёжный, не требующий ручной поддержки ключ поиска."""
    digest = hashlib.sha256()
    digest.update(system.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(user.encode("utf-8"))
    return digest.hexdigest()


def load_fixtures(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("entries", {})


def save_fixtures(path: Path, entries: dict[str, dict[str, Any]]) -> None:
    payload = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


_TEXT_PLACEHOLDER = (
    "[DEMO_MODE] Для этого сценария нет записанной фикстуры. "
    "Запишите её через scripts/record_fixtures.py или отключите DEMO_MODE."
)


class DemoLLMClient(LLMClient):
    """Подменяет живой вызов LLM записанным ответом из demo_fixtures.json.
    Заменяет только LLM-объяснения/извлечение сущностей — вся
    детерминированная часть (прогноз CatBoost, скоринг страхования, подбор
    программ гос поддержки, риск-скор) в это не входит и не подменяется:
    она никогда не проходит через LLMClient, а значит, и не через этот
    класс."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or fixtures_path()
        self._entries = load_fixtures(self._path)
        if not self._entries:
            logger.warning(
                "DEMO_MODE включён, но %s пуст или не найден — все LLM-эндпоинты "
                "будут отвечать заглушкой", self._path,
            )

    def generate(self, system: str, user: str, **kwargs) -> str:
        entry = self._entries.get(hash_prompt(system, user))
        if entry is None:
            logger.warning("DEMO_MODE: фикстура не найдена (mode=text) — заглушка")
            return _TEXT_PLACEHOLDER
        return entry["response"]

    def generate_json(self, system: str, user: str, **kwargs) -> dict:
        entry = self._entries.get(hash_prompt(system, user))
        if entry is None:
            logger.warning("DEMO_MODE: фикстура не найдена (mode=json) — пустой объект")
            return {}
        return entry["response"]


class RecordingLLMClient(LLMClient):
    """Оборачивает настоящий LLMClient: пропускает каждый вызов через него и
    запоминает (system, user) -> ответ, чтобы scripts/record_fixtures.py мог
    потом сохранить всё в demo_fixtures.json. `scenario` — просто
    человекочитаемая метка текущей записи, выставляется скриптом перед
    каждым сценарием ради читаемости файла; на сам поиск при воспроизведении
    не влияет (тот идёт по хэшу)."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.scenario: str = "unlabeled"
        self.entries: dict[str, dict[str, Any]] = {}

    def generate(self, system: str, user: str, **kwargs) -> str:
        response = self._inner.generate(system, user, **kwargs)
        self._record("text", system, user, response)
        return response

    def generate_json(self, system: str, user: str, **kwargs) -> dict:
        response = self._inner.generate_json(system, user, **kwargs)
        self._record("json", system, user, response)
        return response

    def _record(self, mode: str, system: str, user: str, response: Any) -> None:
        key = hash_prompt(system, user)
        self.entries[key] = {
            "scenario": self.scenario,
            "mode": mode,
            "system": system,
            "user": user,
            "response": response,
        }
        logger.info("записан вызов: scenario=%s mode=%s key=%s", self.scenario, mode, key[:12])
