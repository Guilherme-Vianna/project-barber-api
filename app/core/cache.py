from collections.abc import Iterable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import TableClause, event
from sqlalchemy.orm import ORMExecuteState, Session
from sqlalchemy.sql import visitors

EPOCH_FIELD = "epoch"
HISTORY_SUFFIX = "_history"


class ResponseCache(Protocol):
    async def lookup(self, key: str) -> tuple[bytes | None, dict[str, str] | None]: ...

    async def store(self, key: str, value: bytes, ttl: int) -> None: ...

    async def invalidate(self, names: Iterable[str]) -> None: ...


@dataclass(slots=True)
class CacheTracker:
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)
    expires_at: datetime | None = None
    cacheable: bool = True


current_tracker: ContextVar[CacheTracker | None] = ContextVar("cache_tracker", default=None)


def track_read(name: str) -> None:
    tracker = current_tracker.get()
    if tracker is not None:
        tracker.reads.add(name)


def track_write(name: str) -> None:
    tracker = current_tracker.get()
    if tracker is not None:
        tracker.writes.add(name)


def cache_until(when: datetime) -> None:
    tracker = current_tracker.get()
    if tracker is not None and (tracker.expires_at is None or when < tracker.expires_at):
        tracker.expires_at = when


def _dependency_name(table_name: str) -> str:
    return table_name.removesuffix(HISTORY_SUFFIX)


def tables_of(statement: Any) -> set[str]:
    return {
        _dependency_name(element.name)
        for element in visitors.iterate(statement)
        if isinstance(element, TableClause)
    }


@event.listens_for(Session, "do_orm_execute")
def _track_execute(state: ORMExecuteState) -> None:
    tracker = current_tracker.get()
    if tracker is None:
        return
    tables = tables_of(state.statement)
    if state.is_select:
        tracker.reads |= tables
        if not tables:
            tracker.cacheable = False
    else:
        tracker.writes |= tables
        tracker.cacheable = False


@event.listens_for(Session, "after_flush")
def _track_flush(session: Session, _: Any) -> None:
    tracker = current_tracker.get()
    if tracker is None:
        return
    for instance in (*session.new, *session.dirty, *session.deleted):
        table = getattr(type(instance), "__table__", None)
        if table is not None:
            tracker.writes.add(_dependency_name(table.name))
            tracker.cacheable = False
