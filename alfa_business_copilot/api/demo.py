from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alfa_agent.llm import LLMClient

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES_PATH = PROJECT_ROOT / "demo_fixtures.json"
DEFAULT_CACHE_PATH = PROJECT_ROOT / "llm_cache.json"

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def is_demo_mode() -> bool:
    return os.environ.get("DEMO_MODE", "").strip().lower() in _TRUE_VALUES


def is_cache_enabled() -> bool:
    """LLM_CACHE по умолчанию включён — в отличие от DEMO_MODE, здесь нужен
    явный отказ (0/false/no/off), а не явное включение."""
    return os.environ.get("LLM_CACHE", "1").strip().lower() not in _FALSE_VALUES


def fixtures_path() -> Path:
    raw = os.environ.get("DEMO_FIXTURES_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_FIXTURES_PATH


def cache_path() -> Path:
    raw = os.environ.get("LLM_CACHE_PATH", "").strip()
    return Path(raw) if raw else DEFAULT_CACHE_PATH


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


class CachingLLMClient(LLMClient):
    """Кэширует ответы настоящего LLMClient по тому же ключу — хэшу пары
    (system, user), — что использует DemoLLMClient/RecordingLLMClient. При
    повторном запросе с точно таким же промптом отдаёт сохранённый ответ без
    обращения к провайдеру; при промахе — идёт в LLM и сохраняет результат.
    Кэш лежит в JSON рядом с demo_fixtures.json (тот же формат, те же
    load_fixtures/save_fixtures) и переживает перезапуск процесса — в
    отличие от DemoLLMClient, здесь не заглушка при промахе, а настоящий
    вызов: кэш — это ускорение и экономия дневного лимита, а не подмена.

    Ключ — hash_prompt(system, user), без mode, как и у DemoLLMClient: если
    бы generate() и generate_json() когда-нибудь отрендерили побайтово
    одинаковый (system, user), второй вызов перезаписал бы запись первого.
    На практике это не происходит — в проекте каждый вызов рендерится своим
    шаблоном (risk_entity_extraction, risk_explanation и т.д.), и текст
    заведомо разный."""

    def __init__(self, inner: LLMClient, path: Path | None = None) -> None:
        self._inner = inner
        self._path = path or cache_path()
        self._lock = threading.Lock()
        self._entries = load_fixtures(self._path)

    def generate(self, system: str, user: str, **kwargs) -> str:
        return self._call("text", self._inner.generate, system, user, **kwargs)

    def generate_json(self, system: str, user: str, **kwargs) -> dict:
        return self._call("json", self._inner.generate_json, system, user, **kwargs)

    def _call(self, mode: str, fn, system: str, user: str, **kwargs):
        key = hash_prompt(system, user)
        with self._lock:
            entry = self._entries.get(key)
        if entry is not None and entry.get("mode") == mode:
            logger.info("LLM cache hit: mode=%s key=%s", mode, key[:12])
            return entry["response"]

        response = fn(system, user, **kwargs)  # промах — идём в LLM по-настоящему

        with self._lock:
            self._entries[key] = {
                "scenario": "cache", "mode": mode, "system": system, "user": user, "response": response,
            }
            save_fixtures(self._path, self._entries)
        logger.info("LLM cache miss, сохранено: mode=%s key=%s", mode, key[:12])
        return response
