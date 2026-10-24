from enum import StrEnum
from typing import Any
from uuid import uuid7

from sqlalchemy import Column, DateTime, Index, String, Table, Uuid, event, inspect, update
from sqlalchemy.orm import Session
from sqlalchemy.types import NullType

from app.models.base import Base, enum_check, string_enum, utc_now

HISTORY_COLUMNS = ("history_id", "operation", "valid_from", "valid_to", "changed_by")
ACTOR_KEY = "actor"


class HistoryOperation(StrEnum):
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


def versioned[ModelT: type[Base]](model: ModelT) -> ModelT:
    source: Table = model.__table__
    clashes = set(HISTORY_COLUMNS) & set(source.columns.keys())
    if clashes:
        raise TypeError(f"{model.__name__} uses reserved history column names: {clashes}")
    untyped = [column.name for column in source.columns if isinstance(column.type, NullType)]
    if untyped:
        raise TypeError(f"{model.__name__} columns need an explicit type: {untyped}")

    history = Table(
        f"{source.name}_history",
        source.metadata,
        Column("history_id", Uuid, primary_key=True, default=uuid7),
        *(Column(column.name, column.type, nullable=column.nullable) for column in source.columns),
        Column("operation", string_enum(HistoryOperation, 6), nullable=False),
        Column("valid_from", DateTime(timezone=True), nullable=False),
        Column("valid_to", DateTime(timezone=True)),
        Column("changed_by", String(128)),
        enum_check("operation", HistoryOperation),
        Index(f"ix_{source.name}_history_id_valid_from", "id", "valid_from"),
    )
    model.__history_table__ = history
    return model


def is_versioned(instance: object) -> bool:
    return hasattr(type(instance), "__history_table__")


def _snapshot(instance: Base) -> dict[str, Any]:
    mapper = inspect(type(instance))
    return {attr.columns[0].name: getattr(instance, attr.key) for attr in mapper.column_attrs}


def _record(session: Session, instance: Base, operation: HistoryOperation) -> None:
    table: Table = type(instance).__history_table__
    now = utc_now()
    connection = session.connection()
    connection.execute(
        update(table)
        .where(table.c.id == instance.id, table.c.valid_to.is_(None))
        .values(valid_to=now)
    )
    connection.execute(
        table.insert().values(
            **_snapshot(instance),
            history_id=uuid7(),
            operation=operation,
            valid_from=now,
            valid_to=now if operation is HistoryOperation.DELETE else None,
            changed_by=session.info.get(ACTOR_KEY),
        )
    )


@event.listens_for(Session, "after_flush")
def _record_history(session: Session, _: Any) -> None:
    for instance in session.new:
        if is_versioned(instance):
            _record(session, instance, HistoryOperation.INSERT)
    for instance in session.dirty:
        if is_versioned(instance) and session.is_modified(instance, include_collections=False):
            _record(session, instance, HistoryOperation.UPDATE)
    for instance in session.deleted:
        if is_versioned(instance):
            _record(session, instance, HistoryOperation.DELETE)
