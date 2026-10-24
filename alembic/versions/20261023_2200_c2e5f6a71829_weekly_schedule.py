from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2e5f6a71829"
down_revision: str | None = "b1d4e5f60718"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _history_columns() -> list[sa.Column]:
    return [
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "operation",
            sa.Enum("insert", "update", "delete", name="historyoperation", native_enum=False),
            nullable=False,
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.String(length=128), nullable=True),
    ]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    for table in ("barbershops", "barbershops_history"):
        op.add_column(
            table,
            sa.Column("slot_minutes", sa.Integer(), server_default=sa.text("30"), nullable=False),
        )
    op.create_check_constraint(
        op.f("ck_barbershops_slot_minutes"), "barbershops", "slot_minutes BETWEEN 5 AND 480"
    )

    op.create_table(
        "working_hours",
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("closes_at > opens_at", name=op.f("ck_working_hours_period")),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name=op.f("ck_working_hours_weekday")),
        sa.ForeignKeyConstraint(
            ["barbershop_id"],
            ["barbershops.id"],
            name=op.f("fk_working_hours_barbershop_id_barbershops"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_working_hours")),
        sa.UniqueConstraint(
            "barbershop_id", "weekday", name=op.f("uq_working_hours_barbershop_id_weekday")
        ),
    )
    op.create_table(
        "working_hours_history",
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=False),
        sa.Column("closes_at", sa.Time(), nullable=False),
        *_history_columns(),
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_working_hours_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_working_hours_history")),
    )
    op.create_index(
        "ix_working_hours_history_id_valid_from",
        "working_hours_history",
        ["id", "valid_from"],
        unique=False,
    )

    for table in ("appointments", "appointments_history"):
        op.add_column(table, sa.Column("barbershop_id", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE appointments a
        SET barbershop_id = t.barbershop_id, starts_at = t.starts_at, ends_at = t.ends_at
        FROM time_slots t
        WHERE t.id = a.time_slot_id
        """
    )
    op.execute(
        """
        UPDATE appointments_history a
        SET barbershop_id = t.barbershop_id, starts_at = t.starts_at, ends_at = t.ends_at
        FROM (
            SELECT DISTINCT ON (id) id, barbershop_id, starts_at, ends_at
            FROM time_slots_history
            ORDER BY id, valid_from DESC
        ) t
        WHERE t.id = a.time_slot_id
        """
    )
    op.execute("DELETE FROM appointments_history WHERE barbershop_id IS NULL")
    for table in ("appointments", "appointments_history"):
        for column in ("barbershop_id", "starts_at", "ends_at"):
            op.alter_column(table, column, nullable=False)

    op.drop_constraint(
        op.f("fk_appointments_time_slot_id_time_slots"), "appointments", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_appointments_time_slot_id"), "appointments", type_="unique")
    op.drop_column("appointments", "time_slot_id")
    op.drop_column("appointments_history", "time_slot_id")
    op.create_foreign_key(
        op.f("fk_appointments_barbershop_id_barbershops"),
        "appointments",
        "barbershops",
        ["barbershop_id"],
        ["id"],
    )
    op.create_unique_constraint(
        op.f("uq_appointments_barbershop_id_starts_at"),
        "appointments",
        ["barbershop_id", "starts_at"],
    )
    op.create_check_constraint(
        op.f("ck_appointments_period"), "appointments", "ends_at > starts_at"
    )

    op.drop_table("time_slots")
    op.drop_index("ix_time_slots_history_id_valid_from", table_name="time_slots_history")
    op.drop_table("time_slots_history")


def downgrade() -> None:
    raise NotImplementedError("Irreversible migration")
