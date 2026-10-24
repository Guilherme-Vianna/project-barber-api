from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f41d5a0c6dec"
down_revision: str | None = "a6c9d0e15c63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appointment_events_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "booked",
                "rescheduled",
                "updated",
                "cancelled",
                name="appointmenteventkind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor",
            sa.Enum(
                "owner", "customer", "absence", name="appointmenteventactor", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_starts_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "operation IN ('insert', 'update', 'delete')",
            name=op.f("ck_appointment_events_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_appointment_events_history")),
    )
    op.create_index(
        "ix_appointment_events_history_id_valid_from",
        "appointment_events_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "appointment_events",
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "booked",
                "rescheduled",
                "updated",
                "cancelled",
                name="appointmenteventkind",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "actor",
            sa.Enum(
                "owner", "customer", "absence", name="appointmenteventactor", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "actor IN ('owner', 'customer', 'absence')", name=op.f("ck_appointment_events_actor")
        ),
        sa.CheckConstraint(
            "kind IN ('booked', 'rescheduled', 'updated', 'cancelled')",
            name=op.f("ck_appointment_events_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["barbershop_id"],
            ["barbershops.id"],
            name=op.f("fk_appointment_events_barbershop_id_barbershops"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_events")),
    )
    op.create_index(
        op.f("ix_appointment_events_appointment_id"),
        "appointment_events",
        ["appointment_id"],
        unique=False,
    )
    op.create_index(
        "ix_appointment_events_barbershop_id_created_at",
        "appointment_events",
        ["barbershop_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_appointment_events_barbershop_id_created_at", table_name="appointment_events")
    op.drop_index(op.f("ix_appointment_events_appointment_id"), table_name="appointment_events")
    op.drop_table("appointment_events")
    op.drop_index(
        "ix_appointment_events_history_id_valid_from", table_name="appointment_events_history"
    )
    op.drop_table("appointment_events_history")
