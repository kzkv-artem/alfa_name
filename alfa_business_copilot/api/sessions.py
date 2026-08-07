from __future__ import annotations

import threading
import uuid
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class SessionStore(Generic[T]):
    """Thread-safe in-memory store keyed by a server-generated session_id.
    Lives only for the API process lifetime — restarting loses all sessions,
    an accepted tradeoff for this demo (no external store needed)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, T] = {}

    def create(self, value: T) -> str:
        session_id = uuid.uuid4().hex
        with self._lock:
            self._data[session_id] = value
        return session_id

    def get(self, session_id: str) -> T | None:
        with self._lock:
            return self._data.get(session_id)

    def set(self, session_id: str, value: T) -> None:
        with self._lock:
            self._data[session_id] = value

    def get_or_create(self, session_id: str | None, default_factory: Callable[[], T]) -> tuple[str, T]:
        with self._lock:
            if session_id and session_id in self._data:
                return session_id, self._data[session_id]
            new_id = session_id or uuid.uuid4().hex
            value = default_factory()
            self._data[new_id] = value
            return new_id, value


acquisition_sessions: SessionStore = SessionStore()
insurance_sessions: SessionStore = SessionStore()
