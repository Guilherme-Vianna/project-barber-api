from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0c7322906dd"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appointment_services_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
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
            name=op.f("ck_appointment_services_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_appointment_services_history")),
    )
    op.create_index(
        "ix_appointment_services_history_id_valid_from",
        "appointment_services_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "appointments_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("time_slot_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=True),
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
            name=op.f("ck_appointments_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_appointments_history")),
    )
    op.create_index(
        "ix_appointments_history_id_valid_from",
        "appointments_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "barbershops",
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_barbershops")),
        sa.UniqueConstraint("cnpj", name=op.f("uq_barbershops_cnpj")),
    )
    op.create_index(
        op.f("ix_barbershops_firebase_uid"), "barbershops", ["firebase_uid"], unique=True
    )
    op.create_table(
        "barbershops_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=False),
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
            name=op.f("ck_barbershops_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_barbershops_history")),
    )
    op.create_index(
        "ix_barbershops_history_id_valid_from",
        "barbershops_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "services_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
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
            name=op.f("ck_services_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_services_history")),
    )
    op.create_index(
        "ix_services_history_id_valid_from", "services_history", ["id", "valid_from"], unique=False
    )
    op.create_table(
        "time_slots_history",
        sa.Column("history_id", sa.Uuid(), nullable=False),
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("ck_time_slots_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_time_slots_history")),
    )
    op.create_index(
        "ix_time_slots_history_id_valid_from",
        "time_slots_history",
        ["id", "valid_from"],
        unique=False,
    )
    op.create_table(
        "services",
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.CheckConstraint("price >= 0", name=op.f("ck_services_price")),
        sa.ForeignKeyConstraint(
            ["barbershop_id"],
            ["barbershops.id"],
            name=op.f("fk_services_barbershop_id_barbershops"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("barbershop_id", "name", name=op.f("uq_services_barbershop_id_name")),
    )
    op.create_table(
        "time_slots",
        sa.Column("barbershop_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_time_slots_period")),
        sa.ForeignKeyConstraint(
            ["barbershop_id"],
            ["barbershops.id"],
            name=op.f("fk_time_slots_barbershop_id_barbershops"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_time_slots")),
        sa.UniqueConstraint(
            "barbershop_id", "starts_at", name=op.f("uq_time_slots_barbershop_id_starts_at")
        ),
    )
    op.create_table(
        "appointments",
        sa.Column("time_slot_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=150), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["time_slot_id"],
            ["time_slots.id"],
            name=op.f("fk_appointments_time_slot_id_time_slots"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
        sa.UniqueConstraint("time_slot_id", name=op.f("uq_appointments_time_slot_id")),
    )
    op.create_table(
        "appointment_services",
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
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
        sa.CheckConstraint("price >= 0", name=op.f("ck_appointment_services_price")),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_appointment_services_appointment_id_appointments"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_appointment_services_service_id_services"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_services")),
        sa.UniqueConstraint(
            "appointment_id",
            "service_id",
            name=op.f("uq_appointment_services_appointment_id_service_id"),
        ),
    )
    op.create_index(
        op.f("ix_appointment_services_service_id"),
        "appointment_services",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_appointment_services_service_id"), table_name="appointment_services")
    op.drop_table("appointment_services")
    op.drop_table("appointments")
    op.drop_table("time_slots")
    op.drop_table("services")
    op.drop_index("ix_time_slots_history_id_valid_from", table_name="time_slots_history")
    op.drop_table("time_slots_history")
    op.drop_index("ix_services_history_id_valid_from", table_name="services_history")
    op.drop_table("services_history")
    op.drop_index("ix_barbershops_history_id_valid_from", table_name="barbershops_history")
    op.drop_table("barbershops_history")
    op.drop_index(op.f("ix_barbershops_firebase_uid"), table_name="barbershops")
    op.drop_table("barbershops")
    op.drop_index("ix_appointments_history_id_valid_from", table_name="appointments_history")
    op.drop_table("appointments_history")
    op.drop_index(
        "ix_appointment_services_history_id_valid_from", table_name="appointment_services_history"
    )
    op.drop_table("appointment_services_history")
