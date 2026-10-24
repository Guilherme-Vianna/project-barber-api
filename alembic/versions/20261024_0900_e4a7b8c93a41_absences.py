from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a7b8c93a41"
down_revision: str | None = "d3f6a7b82930"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "absences",
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
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_absences_period")),
        sa.ForeignKeyConstraint(
            ["barbershop_id"],
            ["barbershops.id"],
            name=op.f("fk_absences_barbershop_id_barbershops"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_absences")),
    )
    op.create_index(op.f("ix_absences_barbershop_id"), "absences", ["barbershop_id"], unique=False)
    op.create_table(
        "absences_history",
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
            name=op.f("ck_absences_history_operation"),
        ),
        sa.PrimaryKeyConstraint("history_id", name=op.f("pk_absences_history")),
    )
    op.create_index(
        "ix_absences_history_id_valid_from", "absences_history", ["id", "valid_from"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_absences_history_id_valid_from", table_name="absences_history")
    op.drop_table("absences_history")
    op.drop_index(op.f("ix_absences_barbershop_id"), table_name="absences")
    op.drop_table("absences")
